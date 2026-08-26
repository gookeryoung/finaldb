"""SQLite 存储层：连接管理、建表、批量写入与元数据查询。

全部使用参数化 SQL；表名/列名等标识符经 :func:`validate_identifier`
白名单校验（``[A-Za-z_][A-Za-z0-9_]*``）后再拼接，杜绝注入。
"""

from __future__ import annotations

import re
import sqlite3
from collections.abc import Iterable, Sequence
from pathlib import Path

from finaldb.core.exceptions import TableExistsError

__all__ = [
    "ColumnInfo",
    "TableInfo",
    "column_infos",
    "connect",
    "create_table",
    "drop_table",
    "fetch_preview",
    "find_free_table_name",
    "infer_sql_type",
    "insert_rows",
    "quote_identifier",
    "row_count_of",
    "table_exists",
    "table_infos",
    "table_names",
    "validate_identifier",
    "validate_type",
]

# 批量插入的 executemany 分片大小：兼顾内存与事务效率
_BATCH_SIZE = 1000

# 标识符黑名单：禁止引号/空白/控制字符（Unicode 字母数字允许，如中文表名）
_IDENTIFIER_ANY_FORBIDDEN_RE = re.compile(r"[\"'\s\x00-\x1f\x7f]")


class ColumnInfo:
    """表的列元数据（名称 + SQLite 类型亲和性）。."""

    __slots__ = ("name", "sql_type")

    def __init__(self, name: str, sql_type: str) -> None:
        """初始化列元数据。

        :param name: 列名（须通过标识符校验）
        :param sql_type: SQLite 类型（INTEGER/REAL/TEXT）
        """
        self.name = name
        self.sql_type = sql_type

    def __repr__(self) -> str:
        """可读表示（含关键字段）。."""
        return f"ColumnInfo(name={self.name!r}, sql_type={self.sql_type!r})"

    def __eq__(self, other: object) -> bool:
        """按 name 与 sql_type 判等。"""
        if not isinstance(other, ColumnInfo):
            return NotImplemented
        return self.name == other.name and self.sql_type == other.sql_type

    def __hash__(self) -> int:
        """与 __eq__ 一致的哈希（name + sql_type）。"""
        return hash((self.name, self.sql_type))


class TableInfo:
    """表的完整元数据（名称 + 列 + 行数）。."""

    __slots__ = ("columns", "name", "row_count")

    def __init__(self, name: str, columns: list[ColumnInfo], row_count: int) -> None:
        """初始化表元数据。

        :param name: 表名
        :param columns: 列元数据列表
        :param row_count: 行数（COUNT(*)）
        """
        self.name = name
        self.columns = columns
        self.row_count = row_count

    def __repr__(self) -> str:
        """可读表示（含关键字段）。."""
        return f"TableInfo(name={self.name!r}, columns={self.columns!r}, row_count={self.row_count})"


def connect(db_path: Path) -> sqlite3.Connection:
    """打开（或创建）SQLite 数据库连接。

    :param db_path: 数据库文件路径（父目录须存在）
    :return: 已开启外键约束的连接
    """
    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def validate_identifier(name: str) -> str:
    """校验表名/列名合法性，不合法即抛 :class:`ValueError`。

    允许 Unicode 字母数字（含中文）；禁止引号、空白与控制字符。

    :param name: 待校验标识符
    :return: 原样返回合法标识符
    """
    if not name or _IDENTIFIER_ANY_FORBIDDEN_RE.search(name):
        raise ValueError(f"非法标识符: {name!r}")
    return name


def quote_identifier(name: str) -> str:
    """校验并转义标识符为 SQL 片段（双引号包裹）。

    :param name: 待转义标识符
    :return: 形如 ``"name"`` 的 SQL 片段
    """
    return '"' + validate_identifier(name) + '"'


def infer_sql_type(values: Sequence[object]) -> str:
    """根据样本值推断 SQLite 列类型（INTEGER > REAL > TEXT）。

    规则：全为 int（不含 bool）→ INTEGER；全为 int/float 混合（含至少一个
    float，或空样本）→ REAL 其余情况（含 None 混合、字符串、日期等）→ TEXT。
    空列表返回 TEXT（建表时无样本可依）。

    :param values: 该列的样本值
    :return: SQLite 类型字符串
    """
    if not values:
        return "TEXT"
    saw_float = False
    for v in values:
        if v is None:
            return "TEXT"
        if isinstance(v, bool):
            return "TEXT"
        if isinstance(v, int):
            continue
        if isinstance(v, float):
            saw_float = True
            continue
        return "TEXT"
    return "REAL" if saw_float else "INTEGER"


def create_table(
    conn: sqlite3.Connection,
    table: str,
    columns: Sequence[str],
    sql_types: Sequence[str],
) -> None:
    """建表（若表已存在抛 :class:`TableExistsError`）。

    :param conn: 数据库连接
    :param table: 表名
    :param columns: 列名列表
    :param sql_types: 与 columns 等长的类型列表
    """
    if table_exists(conn, table):
        raise TableExistsError(f"表已存在: {table}")
    if len(columns) != len(sql_types):
        raise ValueError("columns 与 sql_types 长度不一致")
    if not columns:
        raise ValueError("至少需要一列")
    if len(set(columns)) != len(columns):
        raise ValueError(f"列名重复: {columns}")
    defs = ", ".join(f"{quote_identifier(col)} {validate_type(t)}" for col, t in zip(columns, sql_types, strict=False))
    conn.execute(f"CREATE TABLE {quote_identifier(table)} ({defs})")
    conn.commit()


def validate_type(sql_type: str) -> str:
    """校验 SQLite 列类型亲和性（仅允许 INTEGER/REAL/TEXT）。."""
    if sql_type not in ("INTEGER", "REAL", "TEXT"):
        raise ValueError(f"非法列类型: {sql_type!r}")
    return sql_type


def insert_rows(
    conn: sqlite3.Connection,
    table: str,
    columns: Sequence[str],
    rows: Iterable[Sequence[object]],
) -> int:
    """事务内分批插入行，返回实际插入行数。

    :param conn: 数据库连接
    :param table: 目标表
    :param columns: 目标列
    :param rows: 行迭代器（每行与 columns 等长）
    :return: 插入行数
    """
    col_sql = ", ".join(quote_identifier(c) for c in columns)
    placeholders = ", ".join("?" for _ in columns)
    insert_sql = f"INSERT INTO {quote_identifier(table)} ({col_sql}) VALUES ({placeholders})"
    count = 0
    batch: list[Sequence[object]] = []
    with conn:  # 单事务：失败整体回滚
        for row in rows:
            batch.append(row)
            if len(batch) >= _BATCH_SIZE:
                conn.executemany(insert_sql, batch)
                count += len(batch)
                batch = []
        if batch:
            conn.executemany(insert_sql, batch)
            count += len(batch)
    return count


def drop_table(conn: sqlite3.Connection, table: str) -> None:
    """删除表（不存在时静默跳过）。."""
    if table_exists(conn, table):
        conn.execute(f"DROP TABLE {quote_identifier(table)}")
        conn.commit()


def table_exists(conn: sqlite3.Connection, table: str) -> bool:
    """判断表是否存在（sqlite_master 查询）。."""
    cur = conn.execute("SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?", (table,))
    return cur.fetchone() is not None


def table_infos(conn: sqlite3.Connection) -> list[TableInfo]:
    """列出库内全部用户表的元数据（按名称排序）。."""
    cur = conn.execute("SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%' ORDER BY name")
    infos = []
    for (name,) in cur.fetchall():
        infos.append(TableInfo(name, column_infos(conn, name), row_count_of(conn, name)))
    return infos


def column_infos(conn: sqlite3.Connection, table: str) -> list[ColumnInfo]:
    """读取指定表的列元数据（PRAGMA table_info）。."""
    cur = conn.execute(f"PRAGMA table_info({quote_identifier(table)})")
    return [ColumnInfo(row[1], row[2]) for row in cur.fetchall()]


def row_count_of(conn: sqlite3.Connection, table: str) -> int:
    """统计指定表行数（COUNT(*)）。."""
    cur = conn.execute(f"SELECT COUNT(*) FROM {quote_identifier(table)}")
    return int(cur.fetchone()[0])


def table_names(conn: sqlite3.Connection) -> list[str]:
    """列出库内全部用户表名（按名称排序）。."""
    cur = conn.execute("SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%' ORDER BY name")
    return [row[0] for row in cur.fetchall()]


def find_free_table_name(conn: sqlite3.Connection, base: str) -> str:
    """为 base 找到不冲突的表名：base / base_2 / base_3 ...

    :param conn: 数据库连接
    :param base: 期望表名（须为合法标识符）
    :return: 首个未占用的表名
    """
    validate_identifier(base)
    if not table_exists(conn, base):
        return base
    i = 2
    while table_exists(conn, f"{base}_{i}"):
        i += 1
    return f"{base}_{i}"


def fetch_preview(
    conn: sqlite3.Connection,
    table: str,
    limit: int = 200,
) -> tuple[list[str], list[tuple[object, ...]]]:
    """读取表前 limit 行用于界面预览。

    :param conn: 数据库连接
    :param table: 表名
    :param limit: 最多读取行数
    :return: (列名列表, 行元组列表)
    """
    names = [c.name for c in column_infos(conn, table)]
    if not names:
        return [], []
    col_sql = ", ".join(quote_identifier(c) for c in names)
    cur = conn.execute(f"SELECT {col_sql} FROM {quote_identifier(table)} LIMIT ?", (limit,))
    return names, cur.fetchall()
