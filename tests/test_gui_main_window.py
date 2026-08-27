"""主窗口 Widgets 测试：页面装配、导航切换、侧边栏折叠与暗色开关。."""

from __future__ import annotations

from typing import Any, Tuple  # noqa: UP035  # 3.8 运行时下标兼容

import pytest

from finaldb.gui.widgets.main_window import PAGE_ORDER

pytestmark = pytest.mark.gui

# main_window fixture 元组：(主窗口, 主题, 工作区/清洗/合并/编辑/统计/关于控制器)
WindowFixture = Tuple[Any, ...]  # noqa: UP006  # 3.8 运行时下标兼容


def test_window_assembles_four_pages(main_window: WindowFixture) -> None:
    """主窗口装配四页且默认停在数据页。."""
    window, *_rest = main_window
    assert window.stack.count() == len(PAGE_ORDER) == 4
    assert set(window.pages) == set(PAGE_ORDER)
    assert window.current_page() == "data"


def test_set_current_page_roundtrip(main_window: WindowFixture) -> None:
    """set_current_page 依序切换全部页面，未知标识被忽略。."""
    window, *_rest = main_window
    for page_id in PAGE_ORDER:
        window.set_current_page(page_id)
        assert window.current_page() == page_id
    window.set_current_page("nope")
    assert window.current_page() == "about"


def test_sidebar_button_switches_page(main_window: WindowFixture) -> None:
    """点击侧边栏导航按钮触发页面切换并保持选中态（其余按钮取消选中）。."""
    window, *_rest = main_window
    button = window.sidebar._buttons["stats"]
    button.click()
    assert window.current_page() == "stats"
    assert button.isChecked()
    # 互斥组：旧页按钮激活态被清除，不残留
    assert not window.sidebar._buttons["data"].isChecked()


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
    badge = window.sidebar._buttons["data"]._badge
    assert "#7AA2F7" in badge.styleSheet()
    check.setChecked(False)
    assert theme.is_dark() is False
    assert "#0366D6" in badge.styleSheet()
