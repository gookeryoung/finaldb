"""MergePage QML 冒烟测试：页面加载、模式切换、表/列联动与同步合并。."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from PySide2.QtGui import QGuiApplication
from PySide2.QtQuick import QQuickItem

from tests.conftest import find_sidebar, qml_set_prop

pytestmark = pytest.mark.gui

# qml_engine fixture 元组：(引擎, 主题, 根窗口, 工作区/预览/清洗/合并/历史控制器)
QmlFixture = tuple[Any, Any, Any, Any, Any, Any, Any, Any]


def test_mergepage_loads(qml_engine: QmlFixture) -> None:
    """切换到合并去重页后 MergePage 成功创建且默认纵向合并模式。"""
    _engine, _theme, root, *_rest = qml_engine
    sidebar = find_sidebar(root)
    qml_set_prop(sidebar, "currentPage", "merge")
    QGuiApplication.processEvents()
    merge_page = root.findChild(QQuickItem, "mergePage")
    assert merge_page is not None, "MergePage 未加载"
    qml_set_prop(sidebar, "currentPage", "home")
    QGuiApplication.processEvents()


def test_mergepage_binding_and_apply(qml_engine: QmlFixture, tmp_path: Path) -> None:
    """工作区建表后 MergePage 联动：表加载 → 键列加载 → 同步合并。."""
    _engine, _theme, root, ws, _pv, _cl, mg, *_rest = qml_engine
    # 准备工作区与数据
    ws.create_workspace("merge-bind")
    csv = tmp_path / "d.csv"
    csv.write_text("name,age\n甲,30\n乙,25\n乙,25\n", "utf-8")
    ws.import_file_sync(str(csv))
    QGuiApplication.processEvents()

    # 切到合并页触发加载
    sidebar = find_sidebar(root)
    qml_set_prop(sidebar, "currentPage", "merge")
    QGuiApplication.processEvents()

    # 控制器直连：加载表/列
    workspace_path = ws.currentWorkspacePath
    mg.load_tables(workspace_path)
    assert mg.tablesModel.rowCount() == 1
    mg.load_columns(workspace_path, "d")
    assert mg.dedupColumnsModel.rowCount() == 2
    mg.load_join_columns(workspace_path, "d", "d")
    assert mg.leftColumnsModel.rowCount() == 2
    assert mg.rightColumnsModel.item_at(1) == "age"

    # 同步去重落库成功（键列拼接传参）
    mg.apply_dedup_sync(workspace_path, "d", "name", "")
    QGuiApplication.processEvents()
    mg.load_tables(workspace_path)
    assert mg.tablesModel.rowCount() == 2
    names = [mg.tablesModel.table_at(i) for i in range(2)]
    assert "d" in names and "d_dedup" in names

    qml_set_prop(sidebar, "currentPage", "home")
    QGuiApplication.processEvents()
