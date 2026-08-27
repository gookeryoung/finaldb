"""app.py 入口装配测试：字体、主题应用与主窗口构造。."""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.gui


def test_apply_global_font(qapp: object) -> None:
    """apply_global_font 应设置应用级字体且不抛异常。."""
    from PySide2.QtWidgets import QApplication

    from finaldb.app import apply_global_font

    app = QApplication.instance()
    assert app is not None
    apply_global_font(app)
    # 字体族回退列表首项应为平台默认字体
    families = app.font().families()
    assert isinstance(families, list)


def test_apply_theme(qapp: object) -> None:
    """apply_theme 应把当前主题 QSS 应用到应用。."""
    from PySide2.QtWidgets import QApplication

    from finaldb.app import apply_theme
    from finaldb.gui.theme import ThemeManager

    app = QApplication.instance()
    assert app is not None
    theme = ThemeManager()
    apply_theme(app, theme)
    assert app.styleSheet()
    assert "#0366D6" in app.styleSheet()


def test_create_app_assembles_window(qapp: object) -> None:
    """create_app 应返回 (应用, 主窗口, 主题) 且默认浅色停在数据源页。."""
    from PySide2.QtWidgets import QApplication

    from finaldb.app import create_app

    app, window, theme = create_app([])
    assert app is QApplication.instance()
    assert window is not None
    assert theme is not None
    assert theme.is_dark() is False
    assert window.current_page() == "home"
    assert window.stack.count() == 8


def test_create_app_theme_change_rebuilds_qss(qapp: object) -> None:
    """create_app 内部连接主题切换：暗色后应用样式表更新。."""

    from finaldb.app import create_app

    app, _window, theme = create_app([])
    theme.set_dark(True)
    assert "#7AA2F7" in app.styleSheet()
