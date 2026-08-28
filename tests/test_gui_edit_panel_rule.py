"""编辑面板键规则条与状态栏测试：规则定义交互 + 键列标识 + 保存状态显示。."""

from __future__ import annotations

import tempfile
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from PySide2.QtCore import Qt

from finaldb.core.storage.database import connect, create_table, insert_rows
from finaldb.gui.controllers.editing_controller import EditingController
from finaldb.gui.theme import ThemeManager
from finaldb.gui.widgets.pages.edit_panel import EditPanel

pytestmark = pytest.mark.gui


@pytest.fixture()
def panel(qapp: Any) -> Iterator[tuple[EditPanel, EditingController, Path]]:
    """建好演示表的编辑面板（嵌入数据页场景）。."""
    with tempfile.TemporaryDirectory() as tmp:
        ws = Path(tmp)
        conn = connect(ws / "data.db")
        create_table(conn, "t", ["id", "name"], ["INTEGER", "TEXT"])
        insert_rows(conn, "t", ["id", "name"], [(1, "甲"), (2, "乙")])
        conn.close()
        controller = EditingController()
        controller.load_tables(str(ws))
        controller.open_table("t")
        theme = ThemeManager()
        yield EditPanel(theme, controller), controller, ws


def test_rule_bar_toggle_and_apply(panel: tuple[EditPanel, EditingController, Path]) -> None:
    """键规则条：切换显示、应用规则、列头出现键标识。."""
    edit_panel, controller, _ws = panel
    assert edit_panel._rule_bar.isHidden()
    edit_panel._toggle_rule_bar()
    assert not edit_panel._rule_bar.isHidden()
    assert edit_panel._rule_combo.count() == 2
    edit_panel._rule_combo.setCurrentText("id")
    edit_panel._rule_start.setValue(10)
    edit_panel._on_apply_rule()
    rule = controller.key_rule()
    assert rule is not None and rule[0] == "id" and rule[1] == 10  # max(10, 2+1)
    # 应用成功后规则条自动收起（状态经 toast 提示）
    assert edit_panel._rule_bar.isHidden()
    # 列头标识：模型 headerData 追加「·键」
    assert edit_panel._edit.edit_model().headerData(0, Qt.Horizontal) == "id ·键"
    # 追加行自动填键序号 10
    controller.add_row()
    assert edit_panel._edit.edit_model().data(edit_panel._edit.edit_model().index(2, 0)) == "10"


def test_rule_bar_clear(panel: tuple[EditPanel, EditingController, Path]) -> None:
    """清除规则：列头标识消失、规则条回到未定义态。."""
    edit_panel, controller, _ws = panel
    controller.set_key_rule("id", 1)
    edit_panel._toggle_rule_bar()
    edit_panel._edit.clear_key_rule()
    assert controller.key_rule() is None
    assert "未定义键规则" in edit_panel._rule_hint.text()
    assert edit_panel._edit.edit_model().headerData(0, Qt.Horizontal) == "id"


def test_rule_bar_guard_without_table(qapp: Any) -> None:
    """未打开表时切换规则条：提示且不显示。."""
    with tempfile.TemporaryDirectory() as tmp:
        ws = Path(tmp)
        conn = connect(ws / "data.db")
        create_table(conn, "t", ["x"], ["TEXT"])
        conn.close()
        controller = EditingController()
        controller.load_tables(str(ws))
        edit_panel = EditPanel(ThemeManager(), controller)
        edit_panel._toggle_rule_bar()
        assert edit_panel._rule_bar.isHidden()


def test_status_bar_shows_saved(main_window: tuple[Any, ...]) -> None:
    """主窗口状态栏：编辑命令后显示已保存状态。."""
    window, _theme, workspace_ctrl, _clean, _merge, edit_ctrl, *_rest = main_window
    demo = Path(workspace_ctrl.workspace_root()) / "demo"
    demo.mkdir(exist_ok=True)
    conn = connect(demo / "data.db")
    conn.execute("CREATE TABLE t (name TEXT)")
    conn.execute("INSERT INTO t VALUES ('甲')")
    conn.commit()
    conn.close()
    edit_ctrl.load_tables(str(demo))
    edit_ctrl.open_table("t")
    edit_ctrl.add_row()
    label = window.findChild(type(window._saved_text), "statusSaved")
    assert label is not None
    assert label.text().startswith("已保存 ")
