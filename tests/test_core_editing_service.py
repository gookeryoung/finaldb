"""编辑服务测试：即时落库、撤销/重做、栈管理。."""

from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from pathlib import Path

import pytest

from finaldb.core.editing import EditService
from finaldb.core.storage.database import column_infos, connect, create_table, insert_rows, row_count_of
from finaldb.core.storage.editing import fetch_rows


@pytest.fixture()
def service(tmp_path: Path) -> Iterator[EditService]:
    """建好演示表（3 行 3 列）的编辑服务。."""
    conn = connect(tmp_path / "data.db")
    create_table(conn, "t", ["name", "age", "city"], ["TEXT", "INTEGER", "TEXT"])
    insert_rows(conn, "t", ["name", "age", "city"], [("甲", 30, "北京"), ("乙", 25, "上海"), ("丙", 40, "深圳")])
    conn.close()
    yield EditService(tmp_path / "data.db")


def _ro(service: EditService) -> sqlite3.Connection:
    """只读验证用连接（用后须 close）。."""
    return connect(Path(service._db_path))


def _rowids_of(service: EditService) -> list[int]:
    """读全表 rowid。."""
    _, rows, _ = service.fetch_page("t", 0)
    return [r[0] for r in rows]


# ----------------------------- set_cell -----------------------------


def test_set_cell_and_undo_redo(service: EditService) -> None:
    """改单元格 → 撤销还原 → 重做再改。."""
    rowid = _rowids_of(service)[0]
    service.set_cell("t", rowid, "age", "31")
    _, rows, _ = service.fetch_page("t", 0)
    assert rows[0][1] == ("甲", 31, "北京")

    service.undo()
    _, rows, _ = service.fetch_page("t", 0)
    assert rows[0][1] == ("甲", 30, "北京")

    service.redo()
    _, rows, _ = service.fetch_page("t", 0)
    assert rows[0][1] == ("甲", 31, "北京")


def test_set_cell_type_coercion(service: EditService) -> None:
    """INTEGER 列文本转数值、空串置 NULL。."""
    rowid = _rowids_of(service)[0]
    service.set_cell("t", rowid, "age", "")
    _, rows, _ = service.fetch_page("t", 0)
    assert rows[0][1][1] is None


def test_set_cell_bad_text_raises(service: EditService) -> None:
    """非法数值文本报错且不入栈。."""
    rowid = _rowids_of(service)[0]
    with pytest.raises(ValueError):
        service.set_cell("t", rowid, "age", "abc")
    assert not service.can_undo()


def test_set_cell_same_value_no_op(service: EditService) -> None:
    """新旧值相同不登记命令。."""
    rowid = _rowids_of(service)[0]
    service.set_cell("t", rowid, "name", "甲")
    assert not service.can_undo()


# ----------------------------- 行操作 -----------------------------


def test_add_row_undo_redo(service: EditService) -> None:
    """加行 → 撤销删除 → 重做复活（rowid 稳定）。"""
    rowid = service.add_row("t", ("丁", 22, "杭州"))
    assert row_count_of(_connect_ro(service), "t") == 4

    service.undo()
    assert row_count_of(_connect_ro(service), "t") == 3

    service.redo()
    _, rows, _ = service.fetch_page("t", 0)
    assert rows[-1][0] == rowid
    assert rows[-1][1] == ("丁", 22, "杭州")


def test_delete_rows_undo_restores_snapshot(service: EditService) -> None:
    """删行撤销按原 rowid 与原数据复活。."""
    rowids = _rowids_of(service)
    target = rowids[1]
    service.delete_rows("t", [target])
    assert row_count_of(_connect_ro(service), "t") == 2

    service.undo()
    _, rows, _ = service.fetch_page("t", 0)
    restored = [r for r in rows if r[0] == target]
    assert restored == [(target, ("乙", 25, "上海"))]


# ----------------------------- 列操作 -----------------------------


def test_column_ops_undo_redo(service: EditService) -> None:
    """加列/重命名/填值的撤销重做全链路。."""
    rowid = _rowids_of(service)[0]

    # 加列并填值、重命名
    service.add_column("t", "score", "REAL")
    service.set_cell("t", rowid, "score", "99.5")
    service.rename_column("t", "score", "rating")

    # 全部撤销回到初态
    for _ in range(3):
        service.undo()
    conn = _connect_ro(service)
    names = [c.name for c in column_infos(conn, "t")]
    conn.close()
    assert names == ["name", "age", "city"]

    # 全部重做回到终态：列存在且数据恢复
    for _ in range(3):
        service.redo()
    conn = _connect_ro(service)
    names = [c.name for c in column_infos(conn, "t")]
    conn.close()
    assert names == ["name", "age", "city", "rating"]
    _, rows, _ = service.fetch_page("t", 0)
    assert rows[0][1][3] == 99.5


def test_drop_column_undo_restores_data(service: EditService) -> None:
    """删列撤销恢复列及整列数据。."""
    service.drop_column("t", "age")
    conn = _connect_ro(service)
    names = [c.name for c in column_infos(conn, "t")]
    conn.close()
    assert names == ["name", "city"]

    service.undo()
    _, rows, _ = service.fetch_page("t", 0)
    assert [r[1] for r in rows] == [("甲", 30, "北京"), ("乙", 25, "上海"), ("丙", 40, "深圳")]


# ----------------------------- 栈管理 -----------------------------


def test_new_command_clears_redo(service: EditService) -> None:
    """新命令使重做栈失效。."""
    rowid = _rowids_of(service)[0]
    service.set_cell("t", rowid, "age", "31")
    service.undo()
    assert service.can_redo()
    service.set_cell("t", rowid, "name", "赵")
    assert not service.can_redo()


def test_labels(service: EditService) -> None:
    """栈顶描述与空栈语义。."""
    assert service.undo_label() == ""
    rowid = _rowids_of(service)[0]
    service.set_cell("t", rowid, "age", "31")
    assert "t.age" in service.undo_label()
    service.undo()
    assert "t.age" in service.redo_label()
    assert service.undo_label() == ""


def test_undo_empty_raises(service: EditService) -> None:
    """空栈撤销/重做报错。."""
    with pytest.raises(ValueError, match="无可撤销"):
        service.undo()
    with pytest.raises(ValueError, match="无可重做"):
        service.redo()


def test_fetch_page_pagination(service: EditService, tmp_path: Path) -> None:
    """分页读取。."""
    conn = connect(tmp_path / "data.db")
    insert_rows(conn, "t", ["name", "age", "city"], [(f"人{i}", i, "城") for i in range(250)])
    conn.close()
    _, page0, total = service.fetch_page("t", 0)
    assert total == 253
    assert len(page0) == 100
    _, page2, _ = service.fetch_page("t", 2)
    assert len(page2) == 53


def _connect_ro(service: EditService) -> sqlite3.Connection:
    """兼容旧名：只读验证用连接。."""
    return _ro(service)


def test_fetch_rows_returns_rowid(service: EditService) -> None:
    """底层 fetch_rows 返回 rowid 供页面定位。."""
    conn = _connect_ro(service)
    names, rows = fetch_rows(conn, "t")
    conn.close()
    assert names == ["name", "age", "city"]
    assert all(isinstance(r[0], int) and r[0] > 0 for r in rows)
