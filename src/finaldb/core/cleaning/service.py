"""清洗服务：从表读取全量数据 → 应用规则 → 写入新表。."""

from __future__ import annotations

import sqlite3
from collections.abc import Sequence
from dataclasses import dataclass
from itertools import chain, islice

from finaldb.core.cleaning.engine import CleanReport, apply_rules
from finaldb.core.cleaning.rules import CleanRule
from finaldb.core.exceptions import CleanError
from finaldb.core.storage.database import (
    column_infos,
    create_table,
    find_free_table_name,
    infer_sql_type,
    insert_rows,
    quote_identifier,
    table_exists,
)

__all__ = ["CleanSummary", "clean_table"]

# 新表类型的采样行数（与导入服务一致）
_TYPE_SAMPLE_ROWS = 200


@dataclass(frozen=True)
class CleanSummary:
    """清洗落库结果摘要。

    :ivar source: 源表名
    :ivar target: 新表名
    :ivar rows_written: 写入行数
    :ivar report: 清洗统计报告
    """

    source: str
    target: str
    rows_written: int
    report: CleanReport


def clean_table(
    conn: sqlite3.Connection,
    table: str,
    rules: Sequence[CleanRule],
    target: str = "",
) -> CleanSummary:
    """清洗指定表并写入新表（保留源表不动）。

    :param conn: 数据库连接
    :param table: 源表名
    :param rules: 清洗规则列表
    :param target: 新表名（空串自动用 ``{源表}_clean``，冲突时追加序号）
    :return: 清洗摘要（新表名 / 行数 / 报告）
    :raises CleanError: 源表不存在或规则校验失败
    """
    if not table_exists(conn, table):
        raise CleanError(f"表不存在: {table}")
    columns = [c.name for c in column_infos(conn, table)]
    col_sql = ", ".join(quote_identifier(c) for c in columns)
    source_rows = conn.execute(f"SELECT {col_sql} FROM {quote_identifier(table)}")
    transformed, report = apply_rules(columns, iter(source_rows), rules)
    # 消费样本行推断新表列类型（缺失值不参与推断：TO_NUMBER 后的空缺不应把列拉回 TEXT）
    sample = list(islice(transformed, _TYPE_SAMPLE_ROWS))
    sql_types = [_infer_column([row[i] for row in sample]) for i in range(len(columns))]
    target_name = find_free_table_name(conn, target if target else f"{table}_clean")
    create_table(conn, target_name, columns, sql_types)
    rows_written = insert_rows(conn, target_name, columns, chain(sample, transformed))
    return CleanSummary(source=table, target=target_name, rows_written=rows_written, report=report)


def _infer_column(values: list[object]) -> str:
    """单列类型推断（缺失值不参与：空缺不应把数值列拉回 TEXT）。."""
    return infer_sql_type([v for v in values if v is not None])
