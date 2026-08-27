"""编辑模块边界分支测试：页面早退路径、模型守卫、存储与服务边界。."""

from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from pathlib import Path
from typing import Any, Tuple  # noqa: UP035  # 3.8 运行时下标兼容

import pytest
from PySide2.QtCore import Qt

from finaldb.core.editing import EditService
from finaldb.core.storage.database import connect, create_table, insert_rows
from finaldb.core.storage.editing import fetch_rows, insert_row, move_column, revive_row
from finaldb.gui.models.edit_model import EditableTableModel

pytestmark = pytest.mark.gui

WindowFixture = Tuple[Any, ...]  # noqa: UP006  # 3.8 运行时下标兼容


def _reject_edit(*args: object) -> bool:
    """恒拒绝的单元格编辑回调。."""
    return False


def _dialog_cancelled(*_a: object, **_k: object) -> tuple[str, bool]:
    """输入对话框：取消。."""
    return ("", False)


def _dialog_same_name(*_a: object, **_k: object) -> tuple[str, bool]:
    """输入对话框：确认但输入与现有列同名。."""
    return ("name", True)


def _csv(tmp_path: Path, name: str, content: str) -> Path:
    """生成临时 CSV 文件。."""
    f = tmp_path / name
    f.write_text(content, "utf-8")
    return f


# ----------------------------- 模型守卫 -----------------------------


@pytest.fixture()
def model(qapp: object) -> EditableTableModel:
    """装载两行两列数据的编辑模型。."""
    m = EditableTableModel()
    m.reset_data(["a", "b"], [(1, ("x", "y")), (2, ("p", "q"))])
    return m


def test_model_data_guards(model: EditableTableModel) -> None:
    """越界索引与无关角色返回 None。."""
    assert model.data(model.index(5, 0)) is None
    assert model.data(model.index(0, 9)) is None
    assert model.data(model.index(0, 0), Qt.CheckStateRole) is None


def test_model_set_data_guards(model: EditableTableModel) -> None:
    """setData 各守卫分支：无回调/坏角色/坏索引均拒绝。."""
    index = model.index(0, 0)
    # 未注册回调
    assert model.setData(index, "v") is False
    # 无参回调恒 False
    model.set_cell_callback(_reject_edit)
    assert model.setData(index, "v") is False
    # 非 EditRole
    assert model.setData(index, "v", Qt.DisplayRole) is False
    # 越界行/列
    assert model.setData(model.index(9, 0), "v") is False
    assert model.setData(model.index(0, 9), "v") is False


def test_model_rowid_helpers(model: EditableTableModel) -> None:
    """rowid_at/rowids_of 越界跳过。."""
    assert model.rowid_at(0) == 1
    assert model.rowid_at(9) is None
    assert model.rowids_of([0, 9]) == [1]


def test_model_flags_editable(model: EditableTableModel) -> None:
    """单元格含可编辑标志。."""
    flags = model.flags(model.index(0, 0))
    assert bool(flags & Qt.ItemIsEditable)
    assert bool(flags & Qt.ItemIsSelectable)


# ----------------------------- 存储与服务边界 -----------------------------


@pytest.fixture()
def conn(tmp_path: Path) -> Iterator[sqlite3.Connection]:
    """演示表连接。."""
    c = connect(tmp_path / "data.db")
    create_table(c, "t", ["a"], ["TEXT"])
    insert_rows(c, "t", ["a"], [("x",), ("y",)])
    yield c
    c.close()


def test_fetch_rows_unknown_table(conn: sqlite3.Connection) -> None:
    """不存在的表返回空结构。."""
    names, rows = fetch_rows(conn, "nope")
    assert names == [] and rows == []


def test_revive_row_width_mismatch(conn: sqlite3.Connection) -> None:
    """复活行值数量不一致报错。."""
    with pytest.raises(ValueError, match="不一致"):
        revive_row(conn, "t", 10, (1, 2))


def test_insert_row_width_mismatch(conn: sqlite3.Connection) -> None:
    """插入行值数量不一致报错。"""
    with pytest.raises(ValueError, match="不一致"):
        insert_row(conn, "t", (1, 2))


def test_move_column_noop(conn: sqlite3.Connection) -> None:
    """移到原位置为无操作；未知列报错。."""
    move_column(conn, "t", "a", 0)
    from finaldb.core.storage.database import column_infos

    assert [c.name for c in column_infos(conn, "t")] == ["a"]
    with pytest.raises(ValueError, match="列不存在"):
        move_column(conn, "t", "nope", 0)


def test_service_set_cell_missing_row(tmp_path: Path) -> None:
    """行不存在报错。."""
    conn = connect(tmp_path / "data.db")
    create_table(conn, "t", ["a"], ["TEXT"])
    conn.close()
    service = EditService(tmp_path / "data.db")
    with pytest.raises(ValueError, match="行不存在"):
        service.set_cell("t", 999, "a", "v")


def test_service_add_row_with_values(tmp_path: Path) -> None:
    """带初值加行。."""
    conn = connect(tmp_path / "data.db")
    create_table(conn, "t", ["a"], ["TEXT"])
    conn.close()
    service = EditService(tmp_path / "data.db")
    rowid = service.add_row("t", ("甲",))
    _, rows, _ = service.fetch_page("t", 0)
    assert rows[-1] == (rowid, ("甲",))


def test_service_undo_redo_empty_raises(tmp_path: Path) -> None:
    """空栈撤销重做报错。."""
    conn = connect(tmp_path / "data.db")
    create_table(conn, "t", ["a"], ["TEXT"])
    conn.close()
    service = EditService(tmp_path / "data.db")
    with pytest.raises(ValueError, match="无可撤销"):
        service.undo()
    with pytest.raises(ValueError, match="无可重做"):
        service.redo()


def test_service_undo_stack_limit(tmp_path: Path) -> None:
    """撤销栈超限淘汰栈底（最多保留 100 条）。."""
    conn = connect(tmp_path / "data.db")
    create_table(conn, "t", ["a"], ["INTEGER"])
    conn.close()
    service = EditService(tmp_path / "data.db")
    service.add_row("t", (None,))
    from finaldb.core.storage.editing import fetch_rows as fr

    conn = connect(tmp_path / "data.db")
    first_rowid = fr(conn, "t")[1][0][0]
    conn.close()
    for i in range(120):
        service.set_cell("t", first_rowid, "a", str(i))
    # 栈共 121 条（add_row + 120 次 set_cell），淘汰 21 条栈底后恰余 100 条
    for _ in range(100):
        service.undo()
    assert not service.can_undo()
    assert service.can_redo()
    _, rows, _ = service.fetch_page("t", 0)
    # 栈底 set_cell(0..19) 已淘汰：值最多回到第 20 次编辑前（即 19）
    assert rows[0][1][0] == 19


# ----------------------------- 页面早退路径 -----------------------------


def test_edit_page_dialog_early_returns(
    main_window: WindowFixture, tmp_path: Path, qapp: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    """无选中列/取消对话框的各早退分支不产生编辑。"""
    import finaldb.gui.widgets.pages.edit_page as edit_mod

    window, _theme, ws, *_rest = main_window
    window.show()
    ws.create_workspace("edge-ws")
    ws.import_file_sync(str(_csv(tmp_path, "d.csv", "name,age\n甲,30\n")))
    qapp.processEvents()
    window.set_current_page("edit")
    qapp.processEvents()
    page = window.pages["edit"]

    # 未开表时加列/删行/重命名/删列/翻页全部安全无操作
    page._on_add_row()
    page._on_delete_rows()
    page._on_add_column()
    page._on_rename_column()
    page._on_drop_column()
    page._on_prev_page()
    page._on_next_page()

    page._on_table_activated(0)
    qapp.processEvents()

    # 已开表但未选中列：重命名/删列提示
    page._on_rename_column()
    page._on_drop_column()

    # 对话框取消（ok=False）不改结构
    monkeypatch.setattr(edit_mod.QInputDialog, "getText", staticmethod(_dialog_cancelled))
    page._on_add_column()
    page._on_rename_column()
    qapp.processEvents()
    assert page._edit.edit_model().columnCount() == 2

    # 选中列后取消重命名与删列确认
    page._view.setCurrentIndex(page._edit.edit_model().index(0, 0))
    monkeypatch.setattr(edit_mod.QInputDialog, "getText", staticmethod(_dialog_same_name))
    page._on_rename_column()  # 同名早退
    from PySide2.QtWidgets import QMessageBox

    def _answer_no(*_a: object, **_k: object) -> int:
        return QMessageBox.No

    monkeypatch.setattr(edit_mod.QMessageBox, "question", staticmethod(_answer_no))
    page._on_drop_column()  # 确认「否」早退
    qapp.processEvents()
    assert page._edit.edit_model().columnCount() == 2
    window.close()


def test_edit_page_show_without_workspace(main_window: WindowFixture, qapp: Any) -> None:
    """无工作区时页面显示不崩溃。"""
    window, *_rest = main_window
    window.show()
    window.set_current_page("edit")
    qapp.processEvents()
    page = window.pages["edit"]
    page.showEvent(None)  # type: ignore[arg-type]  # 直接调用以覆盖空工作区分支
    qapp.processEvents()
    assert page._table_combo.count() == 0
    window.close()
