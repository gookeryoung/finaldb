"""数据编辑存储层测试：行级 CRUD + 列结构操作 + 旧版兼容路径。."""

from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from pathlib import Path

import pytest

from finaldb.core.storage.database import column_infos, connect, create_table, insert_rows, row_count_of
from finaldb.core.storage.editing import (
    add_column,
    coerce_value,
    delete_rows,
    drop_column,
    fetch_rows,
    insert_row,
    rename_column,
    update_cell,
)


@pytest.fixture()
def conn(tmp_path: Path) -> Iterator[sqlite3.Connection]:
    """建好演示表（3 行 3 列）的连接。."""
    c = connect(tmp_path / "ws.db")
    create_table(c, "t", ["name", "age", "city"], ["TEXT", "INTEGER", "TEXT"])
    insert_rows(c, "t", ["name", "age", "city"], [("甲", 30, "北京"), ("乙", 25, "上海"), ("丙", 40, "深圳")])
    yield c
    c.close()


# ----------------------------- 行级 CRUD -----------------------------


def test_fetch_rows_paged(conn: sqlite3.Connection) -> None:
    """分页读取含 rowid。."""
    names, rows = fetch_rows(conn, "t", offset=1, limit=2)
    assert names == ["name", "age", "city"]
    assert len(rows) == 2
    rowid, values = rows[0]
    assert rowid > 0
    assert values == ("乙", 25, "上海")


def test_update_cell(conn: sqlite3.Connection) -> None:
    """按 rowid 修改单元格。."""
    _, rows = fetch_rows(conn, "t")
    rowid = rows[0][0]
    update_cell(conn, "t", rowid, "age", 31)
    _, after = fetch_rows(conn, "t")
    assert after[0][1] == ("甲", 31, "北京")


def test_update_cell_unknown_column(conn: sqlite3.Connection) -> None:
    """列不存在报错。."""
    with pytest.raises(ValueError, match="列不存在"):
        update_cell(conn, "t", 1, "nope", 1)


def test_insert_row_returns_rowid(conn: sqlite3.Connection) -> None:
    """插入行返回新 rowid。."""
    rowid = insert_row(conn, "t", ("丁", 22, "杭州"))
    assert rowid > 0
    assert row_count_of(conn, "t") == 4
    _, rows = fetch_rows(conn, "t")
    assert rows[-1][1] == ("丁", 22, "杭州")


def test_insert_row_width_mismatch(conn: sqlite3.Connection) -> None:
    """值数量与列数不一致报错。."""
    with pytest.raises(ValueError, match="不一致"):
        insert_row(conn, "t", ("丁", 22))


def test_delete_rows(conn: sqlite3.Connection) -> None:
    """按 rowid 批量删除。."""
    _, rows = fetch_rows(conn, "t")
    count = delete_rows(conn, "t", [rows[0][0], rows[2][0]])
    assert count == 2
    assert row_count_of(conn, "t") == 1


# ----------------------------- 列结构操作 -----------------------------


def test_add_column(conn: sqlite3.Connection) -> None:
    """追加列存量行补 NULL。."""
    add_column(conn, "t", "score", "REAL")
    names = [c.name for c in column_infos(conn, "t")]
    assert names == ["name", "age", "city", "score"]
    _, rows = fetch_rows(conn, "t")
    assert rows[0][1] == ("甲", 30, "北京", None)


def test_add_column_duplicate(conn: sqlite3.Connection) -> None:
    """列名重复报错。."""
    with pytest.raises(ValueError, match="列已存在"):
        add_column(conn, "t", "age")


def test_rename_column(conn: sqlite3.Connection) -> None:
    """重命名列保持数据与 rowid 不变。."""
    _, rows = fetch_rows(conn, "t")
    rowid_before = [r[0] for r in rows]
    rename_column(conn, "t", "age", "years")
    names = [c.name for c in column_infos(conn, "t")]
    assert names == ["name", "years", "city"]
    _, after = fetch_rows(conn, "t")
    assert [r[0] for r in after] == rowid_before
    assert after[0][1] == ("甲", 30, "北京")


def test_rename_column_unknown(conn: sqlite3.Connection) -> None:
    """原列不存在报错。."""
    with pytest.raises(ValueError, match="列不存在"):
        rename_column(conn, "t", "nope", "x")


def test_rename_column_conflict(conn: sqlite3.Connection) -> None:
    """新列名与既有列冲突报错。."""
    with pytest.raises(ValueError, match="列已存在"):
        rename_column(conn, "t", "age", "city")


def test_drop_column(conn: sqlite3.Connection) -> None:
    """删除列保持其余数据与 rowid 不变。."""
    _, rows = fetch_rows(conn, "t")
    rowid_before = [r[0] for r in rows]
    drop_column(conn, "t", "age")
    names = [c.name for c in column_infos(conn, "t")]
    assert names == ["name", "city"]
    _, after = fetch_rows(conn, "t")
    assert [r[0] for r in after] == rowid_before
    assert after[0][1] == ("甲", "北京")


def test_drop_last_column_rejected(conn: sqlite3.Connection) -> None:
    """表仅剩一列时禁止删除。."""
    drop_column(conn, "t", "name")
    drop_column(conn, "t", "city")
    with pytest.raises(ValueError, match="至少需要保留一列"):
        drop_column(conn, "t", "age")


def test_drop_column_unknown(conn: sqlite3.Connection) -> None:
    """列不存在报错。."""
    with pytest.raises(ValueError, match="列不存在"):
        drop_column(conn, "t", "nope")


# ----------------------------- 兼容路径与取值转换 -----------------------------


def test_column_ops_via_rebuild_path(conn: sqlite3.Connection, monkeypatch: pytest.MonkeyPatch) -> None:
    """模拟旧版 SQLite：rename/drop 均走重建表路径且 rowid 稳定。."""
    import finaldb.core.storage.editing as editing_mod

    monkeypatch.setattr(editing_mod, "_sqlite_version", lambda: (3, 24, 0))
    _, rows = fetch_rows(conn, "t")
    rowid_before = [r[0] for r in rows]

    rename_column(conn, "t", "age", "years")
    assert [c.name for c in column_infos(conn, "t")] == ["name", "years", "city"]

    monkeypatch.setattr(editing_mod, "_sqlite_version", lambda: (3, 34, 0))
    drop_column(conn, "t", "city")
    assert [c.name for c in column_infos(conn, "t")] == ["name", "years"]

    _, after = fetch_rows(conn, "t")
    assert [r[0] for r in after] == rowid_before
    assert after[0][1] == ("甲", 30)


def test_coerce_value() -> None:
    """按列类型转换界面输入文本。."""
    assert coerce_value("INTEGER", "42") == 42
    assert coerce_value("REAL", "3.5") == 3.5
    assert coerce_value("TEXT", "甲") == "甲"
    assert coerce_value("INTEGER", "") is None
    assert coerce_value("REAL", "") is None
    with pytest.raises(ValueError):
        coerce_value("INTEGER", "abc")
    with pytest.raises(ValueError):
        coerce_value("REAL", "x.y")
