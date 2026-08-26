"""CleanPage QML 冒烟测试：页面加载、规则配置联动、预览绑定。."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from PySide2.QtGui import QGuiApplication
from PySide2.QtQuick import QQuickItem

from tests.conftest import find_sidebar, qml_set_prop

pytestmark = pytest.mark.gui

# qml_engine fixture 元组：(引擎, 主题, 根窗口, 工作区控制器, 预览控制器, 清洗控制器)
QmlFixture = tuple[Any, Any, Any, Any, Any, Any]


def test_cleanpage_loads(qml_engine: QmlFixture) -> None:
    """切换到数据整理页后 CleanPage 成功创建。."""
    _engine, _theme, root, _ws, _pv, _cl = qml_engine
    sidebar = find_sidebar(root)
    qml_set_prop(sidebar, "currentPage", "clean")
    QGuiApplication.processEvents()
    clean_page = root.findChild(QQuickItem, "cleanPage")
    assert clean_page is not None, "CleanPage 未加载"
    qml_set_prop(sidebar, "currentPage", "home")
    QGuiApplication.processEvents()


def test_cleanpage_rules_and_preview(qml_engine: QmlFixture, tmp_path: Path) -> None:
    """工作区建表后 CleanPage 联动：表加载 → 规则 → 预览。."""
    _engine, _theme, root, ws, _pv, cl = qml_engine
    # 准备工作区与数据
    ws.create_workspace("clean-bind")
    csv = tmp_path / "d.csv"
    csv.write_text("name,age\n 甲 ,30\n乙,\n", "utf-8")
    ws.import_file_sync(str(csv))
    QGuiApplication.processEvents()

    # 切到整理页触发加载
    sidebar = find_sidebar(root)
    qml_set_prop(sidebar, "currentPage", "clean")
    QGuiApplication.processEvents()

    # 控制器直连：加载表/列 → 加规则 → 预览
    workspace_path = ws.currentWorkspacePath
    cl.load_tables(workspace_path)
    cl.load_columns(workspace_path, "d")
    cl.add_rule("trim", "name", "", "", "")
    cl.add_rule("to_number", "age", "", "", "")
    cl.preview(workspace_path, "d")
    QGuiApplication.processEvents()
    assert cl.tablesModel.rowCount() == 1
    assert cl.columnsModel.rowCount() == 2
    assert cl.rulesModel.rowCount() == 2
    assert cl.previewModel.rowCount() == 2
    assert "读入行数: 2" in cl.reportText

    # 同步清洗落库成功
    cl.apply_sync(workspace_path, "d", "")
    QGuiApplication.processEvents()
    assert cl.tablesModel.rowCount() == 1  # load_tables 未重调，仍是导入的 1 张表
    cl.load_tables(workspace_path)
    assert cl.tablesModel.rowCount() == 2
    names = [cl.tablesModel.table_at(i) for i in range(2)]
    assert "d" in names and "d_clean" in names

    qml_set_prop(sidebar, "currentPage", "home")
    QGuiApplication.processEvents()
