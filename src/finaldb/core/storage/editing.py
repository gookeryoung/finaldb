"""数据编辑存储层：行级 CRUD 与列结构操作。

与 :mod:`finaldb.core.storage.database` 的只读/批量导入职责互补，
本模块面向交互式编辑：单元格修改、行增删、列增删改。

列结构操作的兼容策略：RENAME COLUMN 需 SQLite 3.25+、DROP COLUMN 需 3.35+，
低于该版本时自动走重建表路径（显式携带 rowid 复制，保持行标识稳定，
撤销栈的 rowid 引用在列操作前后仍然有效）。
"""

from __future__ import annotations

import sqlite3
from collections.abc import Sequence

from finaldb.core.storage.database import (
    column_infos,
    quote_identifier,
    validate_identifier,
    validate_type,
)

__all__ = [
    "add_column",
    "coerce_value",
    "delete_rows",
    "drop_column",
    "fetch_rows",
    "insert_row",
    "move_column",
    "rename_column",
    "revive_row",
    "update_cell",
]

# 列结构原生 ALTER 支持的最低 SQLite 版本
_RENAME_MIN = (3, 25, 0)
_DROP_MIN = (3, 35, 0)


def _sqlite_version() -> tuple[int, ...]:
    """运行时 SQLite 版本元组。."""
    return sqlite3.sqlite_version_info


def fetch_rows(
    conn: sqlite3.Connection,
    table: str,
    offset: int = 0,
    limit: int = 100,
) -> tuple[list[str], list[tuple[int, tuple[object, ...]]]]:
    """分页读取表数据（含 rowid，编辑页数据源）。

    :param conn: 数据库连接
    :param table: 表名
    :param offset: 起始偏移（LIMIT/OFFSET）
    :param limit: 本页行数上限
    :return: (列名列表, [(rowid, 行值元组), ...])
    """
    names = [c.name for c in column_infos(conn, table)]
    if not names:
        return [], []
    col_sql = ", ".join(quote_identifier(c) for c in names)
    cur = conn.execute(
        f"SELECT rowid, {col_sql} FROM {quote_identifier(table)} LIMIT ? OFFSET ?",
        (limit, offset),
    )
    rows = [(int(r[0]), tuple(r[1:])) for r in cur.fetchall()]
    return names, rows


def update_cell(conn: sqlite3.Connection, table: str, rowid: int, column: str, value: object) -> None:
    """修改指定行指定列的单元格值。

    :param conn: 数据库连接
    :param table: 表名
    :param rowid: 行标识（rowid）
    :param column: 列名
    :param value: 新值（None 表示置空）
    :raises ValueError: 列不存在
    """
    if column not in {c.name for c in column_infos(conn, table)}:
        raise ValueError(f"列不存在: {table}.{column}")
    with conn:
        conn.execute(
            f"UPDATE {quote_identifier(table)} SET {quote_identifier(column)} = ? WHERE rowid = ?",
            (value, rowid),
        )


def insert_row(conn: sqlite3.Connection, table: str, values: Sequence[object]) -> int:
    """插入一行数据，返回新行 rowid。

    :param conn: 数据库连接
    :param table: 表名
    :param values: 与表列等长的值序列
    :return: 新行 rowid
    """
    names = [c.name for c in column_infos(conn, table)]
    if len(values) != len(names):
        raise ValueError(f"值数量 {len(values)} 与列数 {len(names)} 不一致")
    col_sql = ", ".join(quote_identifier(c) for c in names)
    placeholders = ", ".join("?" for _ in names)
    with conn:
        cur = conn.execute(
            f"INSERT INTO {quote_identifier(table)} ({col_sql}) VALUES ({placeholders})",
            tuple(values),
        )
        return int(cur.lastrowid)


def delete_rows(conn: sqlite3.Connection, table: str, rowids: Sequence[int]) -> int:
    """按 rowid 批量删除行，返回实际删除行数。

    :param conn: 数据库连接
    :param table: 表名
    :param rowids: 待删除行标识列表
    :return: 删除行数
    """
    if not rowids:
        return 0
    placeholders = ", ".join("?" for _ in rowids)
    with conn:
        cur = conn.execute(
            f"DELETE FROM {quote_identifier(table)} WHERE rowid IN ({placeholders})",
            tuple(rowids),
        )
        return cur.rowcount


def revive_row(conn: sqlite3.Connection, table: str, rowid: int, values: Sequence[object]) -> None:
    """以指定 rowid 复活一行（撤销删行用，保持行标识稳定）。

    :param conn: 数据库连接
    :param table: 表名
    :param rowid: 原 rowid
    :param values: 与表列等长的值序列
    """
    names = [c.name for c in column_infos(conn, table)]
    if len(values) != len(names):
        raise ValueError(f"值数量 {len(values)} 与列数 {len(names)} 不一致")
    col_sql = ", ".join(quote_identifier(c) for c in names)
    placeholders = ", ".join("?" for _ in names)
    with conn:
        conn.execute(
            f"INSERT INTO {quote_identifier(table)} (rowid, {col_sql}) VALUES (?, {placeholders})",
            (rowid, *values),
        )


def add_column(conn: sqlite3.Connection, table: str, column: str, sql_type: str = "TEXT") -> None:
    """追加新列（默认 TEXT，存量行补 NULL）。

    :param conn: 数据库连接
    :param table: 表名
    :param column: 新列名
    :param sql_type: 列类型（INTEGER/REAL/TEXT）
    """
    validate_identifier(column)
    validate_type(sql_type)
    if column in {c.name for c in column_infos(conn, table)}:
        raise ValueError(f"列已存在: {table}.{column}")
    with conn:
        conn.execute(f"ALTER TABLE {quote_identifier(table)} ADD COLUMN {quote_identifier(column)} {sql_type}")


def rename_column(conn: sqlite3.Connection, table: str, old: str, new: str) -> None:
    """重命名列（旧版 SQLite 自动走重建表兼容路径）。

    :param conn: 数据库连接
    :param table: 表名
    :param old: 原列名
    :param new: 新列名
    """
    columns = column_infos(conn, table)
    names = [c.name for c in columns]
    if old not in names:
        raise ValueError(f"列不存在: {table}.{old}")
    if new in names:
        raise ValueError(f"列已存在: {table}.{new}")
    validate_identifier(new)
    if _sqlite_version() >= _RENAME_MIN:
        with conn:
            conn.execute(
                f"ALTER TABLE {quote_identifier(table)} RENAME COLUMN {quote_identifier(old)} TO {quote_identifier(new)}"
            )
        return
    dest = [(_new_name(c.name, old, new), c.sql_type) for c in columns]
    # 源表仍用旧列名：目标列名与源列名一一对应
    src = [c.name for c in columns]
    _rebuild_with_columns(conn, table, dest, src)


def drop_column(conn: sqlite3.Connection, table: str, column: str) -> None:
    """删除列（旧版 SQLite 自动走重建表兼容路径）。

    :param conn: 数据库连接
    :param table: 表名
    :param column: 待删除列名
    :raises ValueError: 表仅剩一列时不允许删除
    """
    columns = column_infos(conn, table)
    if column not in {c.name for c in columns}:
        raise ValueError(f"列不存在: {table}.{column}")
    if len(columns) == 1:
        raise ValueError("表至少需要保留一列")
    kept = [(c.name, c.sql_type) for c in columns if c.name != column]
    if _sqlite_version() >= _DROP_MIN:
        with conn:
            conn.execute(f"ALTER TABLE {quote_identifier(table)} DROP COLUMN {quote_identifier(column)}")
        return
    _rebuild_with_columns(conn, table, kept)


def coerce_value(sql_type: str, text: str) -> object:
    """按列类型把界面输入文本转为落库值。

    空串 → None；INTEGER/REAL 转数值（失败抛 ValueError 提示格式非法）。

    :param sql_type: 列类型（INTEGER/REAL/TEXT）
    :param text: 界面输入文本
    :return: None/int/float/str
    """
    if text == "":
        return None
    if sql_type == "INTEGER":
        return int(text)
    if sql_type == "REAL":
        return float(text)
    return text


def move_column(conn: sqlite3.Connection, table: str, column: str, position: int) -> None:
    """把列移动到指定位置（撤销删列时恢复列的原始次序）。

    :param conn: 数据库连接
    :param table: 表名
    :param column: 列名
    :param position: 目标位置（0 起，越界钳制到首/末）
    :raises ValueError: 列不存在
    """
    columns = column_infos(conn, table)
    names = [c.name for c in columns]
    if column not in names:
        raise ValueError(f"列不存在: {table}.{column}")
    current = names.index(column)
    target = max(0, min(position, len(names) - 1))
    if target == current:
        return
    rest = [c for c in columns if c.name != column]
    ordered = [*rest[:target], columns[current], *rest[target:]]
    _rebuild_with_columns(conn, table, [(c.name, c.sql_type) for c in ordered])


def _new_name(name: str, old: str, new: str) -> str:
    """重命名映射：old → new，其余原样。."""
    return new if name == old else name


def _rebuild_with_columns(
    conn: sqlite3.Connection,
    table: str,
    columns: Sequence[tuple[str, str]],
    src_names: Sequence[str] | None = None,
) -> None:
    """重建表为指定列结构（显式携带 rowid，保持行标识不变）。

    :param conn: 数据库连接
    :param table: 原表名（重建后保持不变）
    :param columns: 目标列结构 [(列名, 类型), ...]
    :param src_names: 源表中与目标列一一对应的列名（重命名时与目标不同；
        缺省用目标列名。须防 SQLite 双引号字面量回退，列不存在会报错而非静默写字符串）
    """
    if len({c for c, _ in columns}) != len(columns):
        raise ValueError(f"列名重复: {[c for c, _ in columns]}")
    names = [c for c, _ in columns] if src_names is None else list(src_names)
    if len(names) != len(columns):
        raise ValueError("src_names 与 columns 长度不一致")
    tmp = quote_identifier(f"{table}__rebuild")
    defs = ", ".join(f"{quote_identifier(c)} {validate_type(t)}" for c, t in columns)
    dest_sql = ", ".join(quote_identifier(c) for c, _ in columns)
    src_sql = ", ".join(quote_identifier(c) for c in names)
    with conn:
        conn.execute(f"DROP TABLE IF EXISTS {tmp}")
        conn.execute(f"CREATE TABLE {tmp} ({defs})")
        conn.execute(f"INSERT INTO {tmp} (rowid, {dest_sql}) SELECT rowid, {src_sql} FROM {quote_identifier(table)}")
        conn.execute(f"DROP TABLE {quote_identifier(table)}")
        conn.execute(f"ALTER TABLE {tmp} RENAME TO {quote_identifier(table)}")
