"""app.py 入口装配测试：字体、主题应用、设置持久化与主窗口构造。."""

from __future__ import annotations

from collections.abc import Iterator

import pytest

from finaldb.gui.settings import clear_theme_settings

pytestmark = pytest.mark.gui


@pytest.fixture(autouse=True)
def _clean_settings() -> Iterator[None]:
    """每个用例前后清空持久化设置（create_app 会恢复/保存主题状态）。."""
    clear_theme_settings()
    yield
    clear_theme_settings()


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
    """create_app 应返回 (应用, 主窗口, 主题) 且默认浅色停在数据页。."""
    from PySide2.QtWidgets import QApplication

    from finaldb.app import create_app

    app, window, theme = create_app([])
    assert app is QApplication.instance()
    assert window is not None
    assert theme is not None
    assert theme.is_dark() is False
    assert window.current_page() == "data"
    assert window.stack.count() == 4


def test_create_app_theme_change_rebuilds_qss(qapp: object) -> None:
    """create_app 内部连接主题切换：暗色后应用样式表更新。."""

    from finaldb.app import create_app

    app, _window, theme = create_app([])
    theme.set_dark(True)
    assert "#7AA2F7" in app.styleSheet()


def test_create_app_persists_and_restores_theme(qapp: object) -> None:
    """create_app 主题变化即持久化，重启（再次 create_app）恢复设置。."""
    from finaldb.app import create_app
    from finaldb.gui.settings import load_theme_settings

    # 首次启动：切换暗色并调字号 → 即时落盘
    app, _window, theme = create_app([])
    theme.set_dark(True)
    theme.set_base_font_size(17)
    assert load_theme_settings() == (True, 17)
    assert "#7AA2F7" in app.styleSheet()

    # 模拟重启：新应用实例恢复持久化的设置
    app2, _window2, theme2 = create_app([])
    assert theme2.is_dark() is True
    assert theme2.font_size_body() == 17
    assert "#7AA2F7" in app2.styleSheet()
