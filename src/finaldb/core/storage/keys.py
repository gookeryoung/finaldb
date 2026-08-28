"""自增键规则：元表持久化 + 下一键序号生成。

规则按表存储于 ``_finaldb_keycfg`` 元表（列 + 起始值），元表在
:func:`finaldb.core.storage.database.table_infos` 等清单入口统一隐藏。
下一键取「已存最大数值 + 1」与「存储计数器」的较大者，避免删除
最大键行后重号；每次生成后推进存储计数器。
"""

from __future__ import annotations

import sqlite3

from finaldb.core.storage.database import quote_identifier

__all__ = ["CFG_TABLE", "clear_key_rule", "get_key_rule", "next_key", "set_key_rule"]

# 键规则元表名（清单入口统一隐藏 _finaldb_ 前缀表）
CFG_TABLE = "_finaldb_keycfg"


def ensure_cfg_table(conn: sqlite3.Connection) -> None:
    """确保键规则元表存在（幂等）。."""
    conn.execute(
        f"CREATE TABLE IF NOT EXISTS {CFG_TABLE} ("
        '"table" TEXT PRIMARY KEY, "column" TEXT NOT NULL, "next" INTEGER NOT NULL)'
    )
    conn.commit()


def get_key_rule(conn: sqlite3.Connection, table: str) -> tuple[str, int] | None:
    """读取表的键规则。

    :param conn: 数据库连接
    :param table: 表名
    :return: (键列名, 下一序号)；未定义返回 None
    """
    ensure_cfg_table(conn)
    row = conn.execute(f'SELECT "column", "next" FROM {CFG_TABLE} WHERE "table" = ?', (table,)).fetchone()
    return (str(row[0]), int(row[1])) if row is not None else None


def set_key_rule(conn: sqlite3.Connection, table: str, column: str, start: int) -> None:
    """定义/更新表的键规则（下一序号按现有数据与起始值取较大者）。.

    :param conn: 数据库连接
    :param table: 表名
    :param column: 键列名（须存在）
    :param start: 起始序号（用户定义规则的起点）
    """
    ensure_cfg_table(conn)
    nxt = max(start, _max_key_value(conn, table, column) + 1)
    # INSERT OR REPLACE 兼容旧版 SQLite（ON CONFLICT 需 3.24+）
    conn.execute(
        f'INSERT OR REPLACE INTO {CFG_TABLE} ("table", "column", "next") VALUES (?, ?, ?)',
        (table, column, nxt),
    )
    conn.commit()


def clear_key_rule(conn: sqlite3.Connection, table: str) -> None:
    """清除表的键规则（未定义时静默）。."""
    ensure_cfg_table(conn)
    conn.execute(f'DELETE FROM {CFG_TABLE} WHERE "table" = ?', (table,))
    conn.commit()


def next_key(conn: sqlite3.Connection, table: str, column: str) -> int | None:
    """生成并登记下一键序号（无规则返回 None，不推进计数器）。

    :param conn: 数据库连接
    :param table: 表名
    :param column: 键列名
    :return: 下一序号；表未定义规则时 None
    """
    rule = get_key_rule(conn, table)
    if rule is None or rule[0] != column:
        return None
    nxt = max(rule[1], _max_key_value(conn, table, column) + 1)
    conn.execute(f'UPDATE {CFG_TABLE} SET "next" = ? WHERE "table" = ?', (nxt + 1, table))
    conn.commit()
    return nxt


def _max_key_value(conn: sqlite3.Connection, table: str, column: str) -> int:
    """取键列已有数据的最大数值（空列/非数值返回 0）。."""
    cur = conn.execute(f"SELECT {quote_identifier(column)} FROM {quote_identifier(table)}")
    numbers = [r[0] for r in cur.fetchall() if isinstance(r[0], (int, float))]
    return int(max(numbers)) if numbers else 0
