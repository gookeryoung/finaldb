"""合并服务：union（纵向堆叠）、dedup（去重）、join（按键连接）。

三种操作都保留源表不动，结果写入新表；类型按结果样本推断。
"""

from __future__ import annotations

import sqlite3
from collections.abc import Callable, Iterable, Iterator, Sequence
from dataclasses import dataclass
from itertools import chain, islice

from finaldb.core.exceptions import MergeError
from finaldb.core.storage.database import (
    column_infos,
    create_table,
    find_free_table_name,
    infer_sql_type,
    insert_rows,
    quote_identifier,
    table_exists,
)

__all__ = ["JoinSpec", "MergeJob", "MergeSummary", "dedup_table", "join_tables", "union_tables"]

# 结果表类型的采样行数
_TYPE_SAMPLE_ROWS = 200

# 连接方式
_HOW_INNER = "inner"
_HOW_LEFT = "left"


@dataclass(frozen=True)
class MergeSummary:
    """合并/去重结果摘要。

    :ivar target: 新表名
    :ivar rows_written: 写入行数
    :ivar detail: 结果描述（删除重复数 / 来源表 / 匹配统计）
    """

    target: str
    rows_written: int
    detail: str


@dataclass(frozen=True)
class JoinSpec:
    """两表连接参数。

    :ivar left: 左表名
    :ivar right: 右表名
    :ivar left_key: 左表键列
    :ivar right_key: 右表键列
    :ivar how: 连接方式（``inner`` / ``left``）
    """

    left: str
    right: str
    left_key: str
    right_key: str
    how: str = _HOW_INNER


@dataclass(frozen=True)
class MergeJob:
    """合并任务描述（``kind`` 决定字段含义，供后台 Worker 携带参数）。

    :ivar kind: ``union`` / ``dedup`` / ``join``
    :ivar tables: union 的源表列表；dedup 的单表
    :ivar keys: dedup 的键列列表（空 = 全行去重）
    :ivar join: join 模式的连接参数
    :ivar target: 新表名（空串自动命名）
    """

    kind: str
    tables: tuple[str, ...] = ()
    keys: tuple[str, ...] = ()
    join: JoinSpec | None = None
    target: str = ""


def union_tables(
    conn: sqlite3.Connection,
    tables: Sequence[str],
    target: str = "",
) -> MergeSummary:
    """纵向堆叠多表：列按名称对齐（首表列序优先，新列追加，缺失补 None）。

    :param conn: 数据库连接
    :param tables: 源表名列表（至少两张）
    :param target: 新表名（空串自动 ``merged``）
    :return: 合并摘要
    :raises MergeError: 表数量不足或表不存在
    """
    if len(tables) < 2:
        raise MergeError("纵向合并至少需要两张表")
    schemas = _schemas_of(conn, tables)
    columns = _union_columns(schemas)
    rows = chain.from_iterable(
        _reordered_rows(conn, table, cols, columns) for table, cols in zip(tables, schemas, strict=True)
    )
    base = target if target else "merged"
    summary_text = "、".join(tables)
    return _write_result(
        conn,
        columns,
        rows,
        base,
        lambda count: f"已合并 {summary_text} 共 {count} 行",
    )


def dedup_table(
    conn: sqlite3.Connection,
    table: str,
    keys: Sequence[str] = (),
    target: str = "",
) -> MergeSummary:
    """表去重：按 keys 去重（保留首见行）；keys 为空按全行去重。

    :param conn: 数据库连接
    :param table: 源表名
    :param keys: 键列名列表（空 = 全行去重）
    :param target: 新表名（空串自动 ``{源表}_dedup``）
    :return: 去重摘要
    :raises MergeError: 表或键列不存在
    """
    columns = _columns_of(conn, table)
    unknown = [k for k in keys if k not in columns]
    if unknown:
        raise MergeError(f"去重键列不存在: {'、'.join(unknown)}")
    key_indices = [columns.index(k) for k in keys]
    rows = _dedup_rows(_table_rows(conn, table, columns), key_indices)
    base = target if target else f"{table}_dedup"
    return _write_result(
        conn,
        columns,
        rows,
        base,
        lambda count: f"去重完成，写入 {count} 行",
    )


def join_tables(conn: sqlite3.Connection, spec: JoinSpec, target: str = "") -> MergeSummary:
    """两表按键连接：inner（仅匹配）/ left（左表全保留，未匹配补 None）。

    右表同名列（非键）追加 ``_2`` 后缀区分来源。

    :param conn: 数据库连接
    :param spec: 连接参数（左右表、键列、连接方式）
    :param target: 新表名（空串自动 ``{左表}_{右表}``）
    :return: 连接摘要
    :raises MergeError: 表/键列不存在或模式不支持
    """
    left, right = spec.left, spec.right
    left_key, right_key, how = spec.left_key, spec.right_key, spec.how
    if how not in (_HOW_INNER, _HOW_LEFT):
        raise MergeError(f"不支持的连接方式: {how}")
    left_columns = _columns_of(conn, left)
    right_columns = _columns_of(conn, right)
    if left_key not in left_columns:
        raise MergeError(f"左表键列不存在: {left_key}")
    if right_key not in right_columns:
        raise MergeError(f"右表键列不存在: {right_key}")
    # 结果列：左表全部 + 右表非键列（冲突名加 _2，仍冲突继续加序号）
    columns = list(left_columns)
    for col in right_columns:
        if col == right_key:
            continue
        name = col
        seen = set(columns)
        i = 2
        while name in seen:
            name = f"{col}_{i}"
            i += 1
        columns.append(name)
    right_key_index = right_columns.index(right_key)
    right_value_indices = [i for i, c in enumerate(right_columns) if c != right_key]

    # 右表按键建索引（key → 行列表）
    index: dict[object, list[tuple[object, ...]]] = {}
    for row in _table_rows(conn, right, right_columns):
        index.setdefault(row[right_key_index], []).append(row)
    matched = 0

    def joined_rows() -> Iterator[tuple[object, ...]]:
        """左表流式迭代，逐行匹配右表。."""
        nonlocal matched
        for left_row in _table_rows(conn, left, left_columns):
            hits = index.get(left_row[left_columns.index(left_key)], [])
            if hits:
                matched += len(hits)
                for right_row in hits:
                    yield (*left_row, *(right_row[i] for i in right_value_indices))
            elif how == _HOW_LEFT:
                yield (*left_row, *(None for _ in right_value_indices))

    base = target if target else f"{left}_{right}"
    return _write_result(
        conn,
        columns,
        joined_rows(),
        base,
        lambda count: f"连接完成，写入 {count} 行（匹配 {matched} 行）",
    )


# ----------------------------- 内部 -----------------------------


def _columns_of(conn: sqlite3.Connection, table: str) -> list[str]:
    """读取表列名列表（表不存在抛 MergeError）。."""
    if not table_exists(conn, table):
        raise MergeError(f"表不存在: {table}")
    return [c.name for c in column_infos(conn, table)]


def _schemas_of(conn: sqlite3.Connection, tables: Sequence[str]) -> list[list[str]]:
    """读取多表列名列表。."""
    return [_columns_of(conn, t) for t in tables]


def _union_columns(schemas: Sequence[Sequence[str]]) -> list[str]:
    """合并列序：按表顺序收集列名并集（保序去重）。."""
    columns: list[str] = []
    seen: set[str] = set()
    for cols in schemas:
        for col in cols:
            if col not in seen:
                seen.add(col)
                columns.append(col)
    return columns


def _table_rows(conn: sqlite3.Connection, table: str, columns: Sequence[str]) -> Iterator[tuple[object, ...]]:
    """流式读取指定表的全部行（列序 = columns）。."""
    col_sql = ", ".join(quote_identifier(c) for c in columns)
    cur = conn.execute(f"SELECT {col_sql} FROM {quote_identifier(table)}")
    yield from cur


def _reordered_rows(
    conn: sqlite3.Connection,
    table: str,
    source_columns: Sequence[str],
    target_columns: Sequence[str],
) -> Iterator[tuple[object, ...]]:
    """读取表行并按目标列序重排（缺失列补 None）。."""
    index_of = {name: i for i, name in enumerate(source_columns)}
    for row in _table_rows(conn, table, source_columns):
        yield tuple(row[index_of[col]] if col in index_of else None for col in target_columns)


def _dedup_rows(
    rows: Iterable[tuple[object, ...]],
    key_indices: Sequence[int],
) -> Iterator[tuple[object, ...]]:
    """首见保留去重（键索引为空时按全行）。."""
    seen: set[tuple[object, ...]] = set()
    for row in rows:
        key = tuple(row[i] for i in key_indices) if key_indices else row
        if key not in seen:
            seen.add(key)
            yield row


def _write_result(
    conn: sqlite3.Connection,
    columns: Sequence[str],
    rows: Iterable[tuple[object, ...]],
    base_name: str,
    describe: Callable[[int], str],
) -> MergeSummary:
    """推断类型 → 建新表 → 流式写入，返回摘要。."""
    sample = list(islice(rows, _TYPE_SAMPLE_ROWS))
    sql_types = [infer_sql_type([v for v in (row[i] for row in sample) if v is not None]) for i in range(len(columns))]
    target = find_free_table_name(conn, base_name)
    create_table(conn, target, list(columns), sql_types)
    count = insert_rows(conn, target, list(columns), chain(sample, rows))
    return MergeSummary(target=target, rows_written=count, detail=describe(count))
