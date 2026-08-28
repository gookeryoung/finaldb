"""矢量图标工厂测试：SVG 资产渲染、着色与异常路径。."""

from __future__ import annotations

from typing import Any

import pytest

import finaldb.gui.widgets.icons as icons_mod
from finaldb.gui.widgets.icons import ICON_NAMES, build_icon

pytestmark = pytest.mark.gui


def test_all_icons_non_null(qapp: Any) -> None:
    """全部注册图标均可渲染出非空 pixmap（资产完整）。."""
    for name in ICON_NAMES:
        icon = build_icon(name, "#0366D6")
        assert not icon.isNull()
        assert not icon.pixmap(24, 24).isNull()


def test_unknown_icon_returns_block(qapp: Any) -> None:
    """未注册图标名：返回黑色方块占位（不抛异常）。."""
    icon = build_icon("nope", "#000000")
    assert not icon.isNull()
    # 黑方块中心像素为黑色（占位提示）
    img = icon.pixmap(24, 24).toImage()
    assert img.pixel(12, 12) == 0xFF000000


def test_asset_missing_returns_block(qapp: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    """SVG 资产文件缺失时返回黑色方块占位（不抛异常）。."""

    def _no_asset(_filename: str) -> str:
        return ""

    monkeypatch.setattr(icons_mod, "_asset_svg", _no_asset)
    icon = build_icon("undo", "#0366D6")
    assert not icon.isNull()
    img = icon.pixmap(24, 24).toImage()
    assert img.pixel(12, 12) == 0xFF000000


def test_icon_color_changes_pixmap(qapp: Any) -> None:
    """不同主题色渲染的资产图标像素数据不同（着色生效）。"""
    img_a = build_icon("clear_table", "#0366D6").pixmap(24, 24).toImage()
    img_b = build_icon("clear_table", "#E74C3C").pixmap(24, 24).toImage()
    # 逐像素比较（QImage 的 ==/!= 是 Python 标识比较，不可用）
    pixels_a = [img_a.pixel(x, y) for x in range(24) for y in range(24)]
    pixels_b = [img_b.pixel(x, y) for x in range(24) for y in range(24)]
    assert pixels_a != pixels_b
