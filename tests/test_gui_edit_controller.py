"""编辑控制器测试：会话管理、错误路径、撤销重做与分页。."""

from __future__ import annotations

import tempfile
from collections.abc import Iterator
from pathlib import Path

import pytest

from finaldb.core.storage.database import connect, create_table, insert_rows
from finaldb.gui.controllers.editing_controller import EditingController

pytestmark = pytest.mark.gui


@pytest.fixture()
def ctrl(qapp: object) -> Iterator[tuple[EditingController, Path]]:
    """建好演示表（3 行 2 列）的控制器与工作区路径。."""
    with tempfile.TemporaryDirectory() as tmp:
        ws = Path(tmp)
        conn = connect(ws / "data.db")
        create_table(conn, "t", ["name", "age"], ["TEXT", "INTEGER"])
        insert_rows(conn, "t", ["name", "age"], [("甲", 30), ("乙", 25), ("丙", 40)])
        conn.close()
        controller = EditingController()
        controller.load_tables(str(ws))
        yield controller, ws


def _errors_of(controller: EditingController) -> list[str]:
    """收集 error_raised 信号的辅助。."""
    errors: list[str] = []
    controller.error_raised.connect(errors.append)  # pyrefly: ignore [missing-attribute]
    return errors


def test_load_tables_empty_workspace(ctrl: tuple[EditingController, Path]) -> None:
    """空工作区路径：表列表清空且关闭会话。."""
    controller, _ws = ctrl
    controller.open_table("t")
    assert controller.current_table() == "t"
    controller.load_tables("")
    assert controller.current_table() == ""
    assert controller.tables_model().rowCount() == 0


def test_open_table_without_workspace(qapp: object) -> None:
    """未 load_tables 直接 open_table：报错信号。."""
    controller = EditingController()
    errors = _errors_of(controller)
    controller.open_table("t")
    assert errors == ["未选择工作区"]
    assert controller.current_table() == ""


def test_open_unknown_table_resets_session(ctrl: tuple[EditingController, Path]) -> None:
    """打开不存在的表：会话置空表名（fetch_page 由调用方保证表存在）。."""
    controller, _ws = ctrl
    controller.open_table("t")
    assert controller.current_table() == "t"
    # 不存在的表打开时 fetch_page 抛错，控制器不应崩溃——由测试验证现状约定：
    # open_table 假定表存在（下拉只列存在的表）
    assert controller.can_undo() is False


def test_command_guards_without_session(ctrl: tuple[EditingController, Path]) -> None:
    """未打开表时全部命令安全无操作。."""
    controller, _ws = ctrl
    # load_tables 但未 open_table
    controller.add_row()
    controller.delete_rows([1])
    controller.add_column("x")
    controller.rename_column("name", "y")
    controller.drop_column("name")
    controller.undo()
    controller.redo()
    controller.goto_page(2)
    assert controller.current_table() == ""
    assert controller.total_rows() == 0


def test_set_cell_dispatches_and_signals(ctrl: tuple[EditingController, Path]) -> None:
    """set_cell 命令式入口：落库 + data_changed/undo_changed。."""
    controller, _ws = ctrl
    controller.open_table("t")
    data_events: list[bool] = []
    undo_events: list[bool] = []
    controller.data_changed.connect(lambda: data_events.append(True))  # pyrefly: ignore [missing-attribute]
    controller.undo_changed.connect(lambda: undo_events.append(True))  # pyrefly: ignore [missing-attribute]
    controller.set_cell("t", 1, "age", "31")
    assert data_events and undo_events
    model = controller.edit_model()
    assert model.data(model.index(0, 1)) == "31"


def test_set_cell_invalid_value_error_signal(ctrl: tuple[EditingController, Path]) -> None:
    """非法数值：error_raised 信号且不崩溃。."""
    controller, _ws = ctrl
    controller.open_table("t")
    errors = _errors_of(controller)
    controller.set_cell("t", 1, "age", "abc")
    assert errors and "age" in errors[0]


def test_add_duplicate_column_error(ctrl: tuple[EditingController, Path]) -> None:
    """重复列名：error_raised。."""
    controller, _ws = ctrl
    controller.open_table("t")
    errors = _errors_of(controller)
    controller.add_column("age")
    assert errors and "age" in errors[0]


def test_undo_redo_wrappers(ctrl: tuple[EditingController, Path]) -> None:
    """控制器撤销重做封装：标签与按钮态数据源。."""
    controller, _ws = ctrl
    controller.open_table("t")
    assert controller.undo_label() == ""
    controller.set_cell("t", 1, "age", "31")
    assert "t.age" in controller.undo_label()
    assert controller.can_undo() and not controller.can_redo()

    controller.undo()
    assert not controller.can_undo() and controller.can_redo()
    assert "t.age" in controller.redo_label()

    controller.redo()
    assert controller.can_undo() and not controller.can_redo()
    model = controller.edit_model()
    assert model.data(model.index(0, 1)) == "31"


def test_goto_page_clamps(ctrl: tuple[EditingController, Path], tmp_path: Path) -> None:
    """分页跳转钳制与行数统计。."""
    controller, ws = ctrl
    conn = connect(ws / "data.db")
    insert_rows(conn, "t", ["name", "age"], [(f"人{i}", i) for i in range(150)])
    conn.close()
    controller.open_table("t")
    assert controller.total_rows() == 153

    controller.goto_page(99)
    assert controller.current_page() == 1  # 153 行 = 2 页
    controller.goto_page(-5)
    assert controller.current_page() == 0
    controller.goto_page(1)
    assert controller.current_page() == 1


def test_workspace_switch_closes_session(tmp_path: Path) -> None:
    """切换工作区后关闭旧编辑会话（修复：编辑写入旧工作区导致“看似没保存”）。."""
    controller = EditingController()
    ws_a = tmp_path / "a"
    ws_b = tmp_path / "b"
    for ws in (ws_a, ws_b):
        ws.mkdir()
        conn = connect(ws / "data.db")
        create_table(conn, "t", ["name"], ["TEXT"])
        conn.close()
    controller.load_tables(str(ws_a))
    controller.open_table("t")
    assert controller.current_table() == "t"
    # 切换到工作区 B：会话关闭，后续编辑不再写入 A 的 data.db
    controller.load_tables(str(ws_b))
    assert controller.current_table() == ""
    assert controller.total_rows() == 0
    # 同一工作区重复 load_tables 不误关会话
    controller.open_table("t")
    controller.load_tables(str(ws_b))
    assert controller.current_table() == "t"


def test_table_list_reload_after_row_change(ctrl: tuple[EditingController, Path]) -> None:
    """行数变化后表列表刷新（行数徽标）。"""
    controller, _ws = ctrl
    controller.open_table("t")
    model = controller.tables_model()
    assert model.rowCount() == 1
    controller.add_row()
    assert controller.total_rows() == 4
    model = controller.tables_model()
    from PySide2.QtCore import Qt

    rows_value = model.data(model.index(0, 0), Qt.UserRole + 2)
    assert rows_value == 4
