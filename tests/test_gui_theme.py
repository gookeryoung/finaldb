"""ThemeController 令牌与暗色模式切换测试。."""

from __future__ import annotations

import pytest
from PySide2.QtGui import QColor

from finaldb.gui.theme import ThemeController, detect_font_families


@pytest.fixture()
def theme() -> ThemeController:
    """每个用例独立的主题控制器。."""
    return ThemeController()


def test_default_light_mode(theme: ThemeController) -> None:
    """默认应为浅色模式。."""
    assert theme.isDark is False
    assert theme.isLight is True


def test_set_dark_toggles_and_notifies(theme: ThemeController) -> None:
    """setDark 切换后 isDark 翻转且发出 themeChanged 信号。."""
    fired: list[bool] = []
    theme.themeChanged.connect(lambda: fired.append(True))  # pyrefly: ignore [missing-attribute]
    theme.setDark(True)
    assert theme.isDark is True
    assert theme.isLight is False
    assert len(fired) == 1
    # 重复设置同值不重复发信号
    theme.setDark(True)
    assert len(fired) == 1


def test_light_palette(theme: ThemeController) -> None:
    """浅色模式色板应为 GitHub Desktop 风格。."""
    assert theme.colorPrimary == QColor("#0366D6")
    assert theme.colorTextPrimary == QColor("#24292E")
    assert theme.colorBgApp == QColor("#F5F6F8")
    assert theme.colorBgCard == QColor("#FFFFFF")


def test_dark_palette(theme: ThemeController) -> None:
    """暗色模式色板应为 Tokyo Night 风格。."""
    theme.setDark(True)
    assert theme.colorPrimary == QColor("#7AA2F7")
    assert theme.colorTextPrimary == QColor("#E0E0EF")
    assert theme.colorBgApp == QColor("#1A1B26")
    assert theme.colorBgCard == QColor("#1E1F2A")
    assert theme.colorSidebarDark == QColor("#16161E")


def test_fixed_colors(theme: ThemeController) -> None:
    """功能色不随主题切换。."""
    dark_before = (theme.colorDanger, theme.colorWarning, theme.colorSuccess, theme.colorTextOnPrimary)
    theme.setDark(True)
    dark_after = (theme.colorDanger, theme.colorWarning, theme.colorSuccess, theme.colorTextOnPrimary)
    assert dark_before == dark_after


def test_typography_tokens(theme: ThemeController) -> None:
    """字号令牌基于基准 14px 派生。."""
    assert theme.fontSizeBody == 14
    assert theme.fontSizeHeading == 16
    assert theme.fontSizeTitle == 18
    assert theme.fontSizePageTitle == 22
    assert theme.fontSizeCaption == 12
    assert theme.fontSizeSmall == 13


def test_spacing_and_radius_tokens(theme: ThemeController) -> None:
    """间距按 8px 基准网格，圆角 4/6/8。."""
    assert (theme.spacingXs, theme.spacingSm) == (4, 8)
    assert (theme.spacingMd, theme.spacingLg, theme.spacingXl) == (16, 24, 32)
    assert (theme.radiusSm, theme.radiusMd, theme.radiusLg) == (4, 6, 8)
    assert theme.sidebarWidth == 200


def test_detect_font_families_nonempty() -> None:
    """平台字体族探测应返回非空元组且首项为字符串。."""
    families = detect_font_families()
    assert isinstance(families, tuple)
    assert families
    assert all(isinstance(f, str) for f in families)


def test_detect_font_families_windows(monkeypatch: pytest.MonkeyPatch) -> None:
    """Windows 平台应返回微软雅黑优先的字体族。."""
    import finaldb.gui.theme as theme_mod

    monkeypatch.setattr(theme_mod.sys, "platform", "win32")
    families = theme_mod.detect_font_families()
    assert families[0] == "Microsoft YaHei UI"


def test_detect_font_families_darwin(monkeypatch: pytest.MonkeyPatch) -> None:
    """macOS 平台应返回苹方优先的字体族。."""
    import finaldb.gui.theme as theme_mod

    monkeypatch.setattr(theme_mod.sys, "platform", "darwin")
    families = theme_mod.detect_font_families()
    assert families[0] == "PingFang SC"


def test_detect_font_families_linux(monkeypatch: pytest.MonkeyPatch) -> None:
    """Linux 平台应返回思源黑体优先的字体族。"""
    import finaldb.gui.theme as theme_mod

    monkeypatch.setattr(theme_mod.sys, "platform", "linux")
    families = theme_mod.detect_font_families()
    assert families[0] == "Noto Sans CJK SC"
