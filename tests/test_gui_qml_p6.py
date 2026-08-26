"""P6 页面 QML 冒烟测试：统计/设置/关于页加载与统计联动。."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from PySide2.QtGui import QGuiApplication
from PySide2.QtQuick import QQuickItem

from tests.conftest import find_sidebar, qml_set_prop

pytestmark = pytest.mark.gui

# qml_engine fixture 元组：(引擎, 主题, 根窗口, 工作区/预览/清洗/合并/历史/统计/关于控制器)
QmlFixture = tuple[Any, Any, Any, Any, Any, Any, Any, Any, Any, Any]


def test_statspage_loads(qml_engine: QmlFixture) -> None:
    """切换到统计页后 StatsPage 成功创建。."""
    _engine, _theme, root, *_rest = qml_engine
    sidebar = find_sidebar(root)
    qml_set_prop(sidebar, "currentPage", "stats")
    QGuiApplication.processEvents()
    stats_page = root.findChild(QQuickItem, "statsPage")
    assert stats_page is not None, "StatsPage 未加载"
    qml_set_prop(sidebar, "currentPage", "home")
    QGuiApplication.processEvents()


def test_settingspage_loads(qml_engine: QmlFixture) -> None:
    """切换到设置页后 SettingsPage 成功创建且含暗色开关。."""
    _engine, _theme, root, *_rest = qml_engine
    sidebar = find_sidebar(root)
    qml_set_prop(sidebar, "currentPage", "settings")
    QGuiApplication.processEvents()
    settings_page = root.findChild(QQuickItem, "settingsPage")
    assert settings_page is not None, "SettingsPage 未加载"
    assert root.findChild(QQuickItem, "darkSwitch") is not None
    assert root.findChild(QQuickItem, "fontSlider") is not None
    qml_set_prop(sidebar, "currentPage", "home")
    QGuiApplication.processEvents()


def test_aboutpage_loads(qml_engine: QmlFixture) -> None:
    """切换到关于页后 AboutPage 成功创建。."""
    _engine, _theme, root, *_rest = qml_engine
    sidebar = find_sidebar(root)
    qml_set_prop(sidebar, "currentPage", "about")
    QGuiApplication.processEvents()
    about_page = root.findChild(QQuickItem, "aboutPage")
    assert about_page is not None, "AboutPage 未加载"
    qml_set_prop(sidebar, "currentPage", "home")
    QGuiApplication.processEvents()


def test_statspage_summary_binding(qml_engine: QmlFixture, tmp_path: Path) -> None:
    """工作区导入后统计页联动：摘要与表分布加载。."""
    _engine, _theme, root, ws, _pv, _cl, _mg, _hist, stats, _about = qml_engine
    ws.create_workspace("stats-bind")
    csv = tmp_path / "s.csv"
    csv.write_text("name,age\n甲,30\n乙,25\n丙,\n", "utf-8")
    ws.import_file_sync(str(csv))
    QGuiApplication.processEvents()

    sidebar = find_sidebar(root)
    qml_set_prop(sidebar, "currentPage", "stats")
    QGuiApplication.processEvents()

    workspace_path = ws.currentWorkspacePath
    stats.load_stats(workspace_path)
    QGuiApplication.processEvents()
    assert stats.summaryText == "共 1 张表，3 行数据"
    assert stats.statsModel.rowCount() == 1
    first = stats.statsModel.stat_at(0)
    assert first is not None and first.name == "s"

    qml_set_prop(sidebar, "currentPage", "home")
    QGuiApplication.processEvents()
