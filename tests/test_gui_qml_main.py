"""QML 主框架冒烟测试：加载、页面切换、暗色模式联动。."""

from __future__ import annotations

import time
from typing import Any

import pytest
from PySide2.QtCore import QObject
from PySide2.QtGui import QColor, QGuiApplication
from PySide2.QtQuick import QQuickItem

from tests.conftest import find_sidebar, qml_prop, qml_set_prop

pytestmark = pytest.mark.gui

# qml_engine fixture 元组类型：(引擎, 主题控制器, 根窗口)
QmlFixture = tuple[Any, Any, Any]


def _find_child(root: QObject, name: str) -> QQuickItem:
    """按 objectName 查找 QQuickItem，找不到即断言失败。."""
    item = root.findChild(QQuickItem, name)
    assert item is not None, f"未找到 {name}"
    return item


def _pump_events(seconds: float) -> None:
    """驱动事件循环并等待真实时间流逝（供 QML 动画/绑定完成）。."""
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        QGuiApplication.processEvents()
        time.sleep(0.02)


def test_main_qml_loads(qml_engine: QmlFixture) -> None:
    """Main.qml 应成功加载且窗口标题正确。."""
    _engine, _theme, root = qml_engine
    assert qml_prop(root, "title") == "finaldb"


def test_sidebar_default_page(qml_engine: QmlFixture) -> None:
    """侧边栏默认选中数据源页。."""
    _engine, _theme, root = qml_engine
    sidebar = find_sidebar(root)
    assert qml_prop(sidebar, "currentPage") == "home"


def test_sidebar_page_switch(qml_engine: QmlFixture) -> None:
    """切换 currentPage 后内容区 activePage 随之更新。."""
    _engine, _theme, root = qml_engine
    sidebar = find_sidebar(root)
    content = _find_child(root, "contentArea")
    # 切到「合并去重」页
    qml_set_prop(sidebar, "currentPage", "merge")
    QGuiApplication.processEvents()
    assert qml_prop(content, "activePage") == "merge"
    # 切回首页
    qml_set_prop(sidebar, "currentPage", "home")
    QGuiApplication.processEvents()
    assert qml_prop(content, "activePage") == "home"


def test_sidebar_background_binds_theme(qml_engine: QmlFixture) -> None:
    """Python 侧切换暗色模式后侧栏背景色绑定应刷新为深蓝黑。."""
    _engine, theme, root = qml_engine
    bg = _find_child(root, "sidebarBackground")
    assert qml_prop(bg, "color") == QColor("#FFFFFF")
    theme.setDark(True)
    # 背景 Behavior 有 200ms ColorAnimation，轮询等待动画收敛
    expected = QColor("#16161E")
    deadline = time.monotonic() + 2.0
    while qml_prop(bg, "color") != expected:
        assert time.monotonic() < deadline, "暗色切换动画未收敛"
        _pump_events(0.05)
    assert qml_prop(bg, "color") == expected
