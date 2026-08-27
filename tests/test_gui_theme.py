"""ThemeManager 令牌、QSS 生成与暗色模式切换测试。."""

from __future__ import annotations

import pytest

from finaldb.gui.theme import (
    RADIUS_LG,
    RADIUS_MD,
    RADIUS_SM,
    SIDEBAR_WIDTH,
    SPACING_LG,
    SPACING_MD,
    SPACING_SM,
    SPACING_XL,
    SPACING_XS,
    ThemeManager,
    build_qss,
    detect_font_families,
)

# 不随主题切换的功能色名
_FIXED_COLORS = ("danger", "warning", "success", "text_on_primary")


@pytest.fixture()
def theme() -> ThemeManager:
    """每个用例独立的主题管理器。."""
    return ThemeManager()


def test_default_light_mode(theme: ThemeManager) -> None:
    """默认应为浅色模式。."""
    assert theme.is_dark() is False


def test_set_dark_toggles_and_notifies(theme: ThemeManager) -> None:
    """set_dark 切换后 is_dark 翻转且发出 theme_changed 信号。."""
    fired: list[bool] = []
    theme.theme_changed.connect(lambda: fired.append(True))  # pyrefly: ignore [missing-attribute]
    theme.set_dark(True)
    assert theme.is_dark() is True
    assert len(fired) == 1
    # 重复设置同值不重复发信号
    theme.set_dark(True)
    assert len(fired) == 1


def test_light_palette(theme: ThemeManager) -> None:
    """浅色模式色板应为 GitHub Desktop 风格。."""
    assert theme.color("primary") == "#0366D6"
    assert theme.color("text_primary") == "#24292E"
    assert theme.color("bg_app") == "#F5F6F8"
    assert theme.color("bg_card") == "#FFFFFF"


def test_dark_palette(theme: ThemeManager) -> None:
    """暗色模式色板应为 Tokyo Night 风格。."""
    theme.set_dark(True)
    assert theme.color("primary") == "#7AA2F7"
    assert theme.color("text_primary") == "#E0E0EF"
    assert theme.color("bg_app") == "#1A1B26"
    assert theme.color("bg_card") == "#1E1F2A"
    assert theme.color("sidebar") == "#16161E"


def test_fixed_colors(theme: ThemeManager) -> None:
    """功能色不随主题切换。."""
    before = tuple(theme.color(name) for name in _FIXED_COLORS)
    theme.set_dark(True)
    after = tuple(theme.color(name) for name in _FIXED_COLORS)
    assert before == after


def test_palette_switch(theme: ThemeManager) -> None:
    """palette 随暗色模式在两组色板间切换。."""
    light = theme.palette()
    assert light["primary"] == "#0366D6"
    theme.set_dark(True)
    assert theme.palette()["primary"] == "#7AA2F7"


def test_typography_tokens(theme: ThemeManager) -> None:
    """字号令牌基于基准 14px 派生。."""
    assert theme.font_size_body() == 14
    assert theme.font_size_heading() == 16
    assert theme.font_size_title() == 18
    assert theme.font_size_page_title() == 22
    assert theme.font_size_caption() == 12
    assert theme.font_size_small() == 13


def test_spacing_and_radius_constants() -> None:
    """间距按 8px 基准网格，圆角 4/6/8。."""
    assert (SPACING_XS, SPACING_SM) == (4, 8)
    assert (SPACING_MD, SPACING_LG, SPACING_XL) == (16, 24, 32)
    assert (RADIUS_SM, RADIUS_MD, RADIUS_LG) == (4, 6, 8)
    assert SIDEBAR_WIDTH == 200


def test_set_base_font_size(theme: ThemeManager) -> None:
    """set_base_font_size 调整基准字号并发出 theme_changed。."""
    fired: list[bool] = []
    theme.theme_changed.connect(lambda: fired.append(True))  # pyrefly: ignore [missing-attribute]
    theme.set_base_font_size(16)
    assert theme.font_size_body() == 16
    assert theme.font_size_heading() == 18
    assert len(fired) == 1
    # 重复设置同值不重复发信号
    theme.set_base_font_size(16)
    assert len(fired) == 1


def test_set_base_font_size_clamped(theme: ThemeManager) -> None:
    """字号设置钳位到 12~20。."""
    theme.set_base_font_size(4)
    assert theme.font_size_body() == 12
    theme.set_base_font_size(99)
    assert theme.font_size_body() == 20


def test_font_family_matches_platform_default(theme: ThemeManager) -> None:
    """font_family 返回平台默认字体族首项。."""
    assert theme.font_family() == detect_font_families()[0]


def test_build_qss_light(theme: ThemeManager) -> None:
    """浅色 QSS 含主色与基准字号。."""
    qss = build_qss(theme)
    assert "#0366D6" in qss
    assert "font-size: 14px" in qss


def test_build_qss_dark_and_font_size(theme: ThemeManager) -> None:
    """暗色与自定义字号反映到 QSS。."""
    theme.set_dark(True)
    theme.set_base_font_size(16)
    qss = build_qss(theme)
    assert "#7AA2F7" in qss
    assert "font-size: 16px" in qss


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
