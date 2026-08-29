"""自增键规则：元表持久化 + 下一键序号生成。

规则按表存储于 ``_finaldb_keycfg`` 元表（列 + 起始下限），元表在
:func:`finaldb.core.storage.database.table_infos` 等清单入口统一隐藏。
下一键完全由数据驱动：取「键列已存最大数值 + 1」与「定义规则时的
起始下限」的较大者，实时计算——删除行后序号自动回落复用，与界面
展示双向一致。
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
    if row is None:
        return None
    column = str(row[0])
    nxt = max(int(row[1]), _max_key_value(conn, table, column) + 1)
    return (column, nxt)


def set_key_rule(conn: sqlite3.Connection, table: str, column: str, start: int) -> None:
    """定义/更新表的键规则（下一序号按现有数据与起始值取较大者）。.

    :param conn: 数据库连接
    :param table: 表名
    :param column: 键列名（须存在）
    :param start: 起始序号（用户定义规则的起点，作为后续生成的不回落下限）
    """
    ensure_cfg_table(conn)
    # 存用户起始值作为不回落下限；下一序号读取时按当前数据实时计算
    conn.execute(
        f'INSERT OR REPLACE INTO {CFG_TABLE} ("table", "column", "next") VALUES (?, ?, ?)',
        (table, column, start),
    )
    conn.commit()


def clear_key_rule(conn: sqlite3.Connection, table: str) -> None:
    """清除表的键规则（未定义时静默）。."""
    ensure_cfg_table(conn)
    conn.execute(f'DELETE FROM {CFG_TABLE} WHERE "table" = ?', (table,))
    conn.commit()


def next_key(conn: sqlite3.Connection, table: str, column: str) -> int | None:
    """生成下一键序号（无规则返回 None）。

    序号由数据实时驱动，无需登记推进：写入该序号的行落库后，
    后续计算自然前移；删除行后自动回落复用被删的序号。

    :param conn: 数据库连接
    :param table: 表名
    :param column: 键列名
    :return: 下一序号；表未定义规则时 None
    """
    rule = get_key_rule(conn, table)
    if rule is None or rule[0] != column:
        return None
    return rule[1]


def _max_key_value(conn: sqlite3.Connection, table: str, column: str) -> int:
    """取键列已有数据的最大数值（空列/非数值返回 0）。."""
    cur = conn.execute(f"SELECT {quote_identifier(column)} FROM {quote_identifier(table)}")
    numbers = [r[0] for r in cur.fetchall() if isinstance(r[0], (int, float))]
    return int(max(numbers)) if numbers else 0
