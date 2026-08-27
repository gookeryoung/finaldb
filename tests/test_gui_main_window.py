"""主窗口 Widgets 测试：页面装配、导航切换、侧边栏折叠与暗色开关。."""

from __future__ import annotations

from typing import Any

import pytest

from finaldb.gui.widgets.main_window import PAGE_ORDER

pytestmark = pytest.mark.gui

# main_window fixture 元组：(主窗口, 主题, 工作区/预览/清洗/合并/历史/统计/关于控制器)
WindowFixture = tuple[Any, ...]


def test_window_assembles_seven_pages(main_window: WindowFixture) -> None:
    """主窗口装配七页且默认停在数据源页。."""
    window, *_rest = main_window
    assert window.stack.count() == len(PAGE_ORDER) == 7
    assert set(window.pages) == set(PAGE_ORDER)
    assert window.current_page() == "home"


def test_set_current_page_roundtrip(main_window: WindowFixture) -> None:
    """set_current_page 依序切换全部页面，未知标识被忽略。."""
    window, *_rest = main_window
    for page_id in PAGE_ORDER:
        window.set_current_page(page_id)
        assert window.current_page() == page_id
    window.set_current_page("nope")
    assert window.current_page() == "about"


def test_sidebar_button_switches_page(main_window: WindowFixture) -> None:
    """点击侧边栏导航按钮触发页面切换并保持选中态。."""
    window, *_rest = main_window
    button = window.sidebar._buttons["clean"]
    button.click()
    assert window.current_page() == "clean"
    assert button.isChecked()


def test_toggle_sidebar(main_window: WindowFixture, qapp: Any) -> None:
    """toggle_sidebar 折叠/展开侧边栏。."""
    window, *_rest = main_window
    window.show()
    qapp.processEvents()
    assert window.sidebar.isVisible()
    window.toggle_sidebar()
    qapp.processEvents()
    assert not window.sidebar.isVisible()
    window.toggle_sidebar()
    qapp.processEvents()
    assert window.sidebar.isVisible()
    window.close()


def test_sidebar_dark_toggle_switches_theme(main_window: WindowFixture, qapp: Any) -> None:
    """侧边栏暗色开关切换主题并联动导航色块。."""
    from PySide2.QtWidgets import QCheckBox, QFrame

    window, theme, *_rest = main_window
    assert window.sidebar.findChild(QFrame, "darkRow") is not None
    check = window.sidebar.findChild(QCheckBox)
    assert check is not None
    # 勾选侧边栏开关 → 主题切暗色 → 导航色块与暗色行样式联动刷新
    check.setChecked(True)
    qapp.processEvents()
    assert theme.is_dark() is True
    badge = window.sidebar._buttons["home"]._badge
    assert "#7AA2F7" in badge.styleSheet()
    check.setChecked(False)
    assert theme.is_dark() is False
    assert "#0366D6" in badge.styleSheet()
