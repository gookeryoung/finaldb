"""矢量图标工厂与编辑面板按钮图标测试。."""

from __future__ import annotations

from typing import Any

import pytest

import finaldb.gui.widgets.icons as icons_mod
from finaldb.gui.widgets.icons import ICON_NAMES, build_icon

pytestmark = pytest.mark.gui


def test_all_icons_non_null(qapp: Any) -> None:
    """全部注册图标均可绘制出非空 pixmap（SVG 资产与自绘两条路径）。."""
    for name in ICON_NAMES:
        icon = build_icon(name, "#0366D6")
        assert not icon.isNull()
        assert not icon.pixmap(24, 24).isNull()


def test_unknown_icon_raises(qapp: Any) -> None:
    """未注册图标名：抛 ValueError 且提示含原名。."""
    with pytest.raises(ValueError, match="未知图标名称: nope"):
        build_icon("nope", "#000000")


def test_asset_icon_renders(qapp: Any) -> None:
    """SVG 资产图标（undo）按主题色渲染出非空 pixmap。."""
    assert "undo" in icons_mod._ASSET_FILES
    icon = build_icon("undo", "#0366D6")
    assert not icon.isNull()


def test_asset_missing_falls_back_to_draw(qapp: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    """SVG 资产缺失/渲染失败时回退 QPainter 自绘，不抛异常。"""

    def _no_asset(_filename: str) -> str:
        return ""

    # 资产文本为空：视为文件缺失 → 走自绘回退
    monkeypatch.setattr(icons_mod, "_asset_svg", _no_asset)
    icon = build_icon("undo", "#0366D6")
    assert not icon.isNull()


def test_all_fallback_painters_draw(qapp: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    """全部有资产映射的图标在资产缺失时自绘回退均可出图。."""

    def _no_asset(_filename: str) -> str:
        return ""

    monkeypatch.setattr(icons_mod, "_asset_svg", _no_asset)
    for name in (
        "undo",
        "redo",
        "add_row",
        "del_row",
        "add_col",
        "del_col",
        "rename_col",
        "clear_table",
        "import_data",
        "rename",
        "refresh",
        "database",
        "stats",
        "settings",
        "about",
        "moon",
        "sun",
    ):
        icon = build_icon(name, "#0366D6")
        assert not icon.isNull(), f"自绘回退失败: {name}"
        assert not icon.pixmap(24, 24).isNull()


def test_icon_color_changes_pixmap(qapp: Any) -> None:
    """不同主题色渲染的资产图标像素数据不同（着色生效）。"""
    img_a = build_icon("clear_table", "#0366D6").pixmap(24, 24).toImage()
    img_b = build_icon("clear_table", "#E74C3C").pixmap(24, 24).toImage()
    # 逐像素比较（QImage 的 ==/!= 是 Python 标识比较，不可用）
    pixels_a = [img_a.pixel(x, y) for x in range(24) for y in range(24)]
    pixels_b = [img_b.pixel(x, y) for x in range(24) for y in range(24)]
    assert pixels_a != pixels_b


def test_edit_panel_buttons_have_icons(main_window: Any, qapp: Any) -> None:
    """编辑面板工具栏与分页按钮初始化后均带图标。."""
    window, *_rest = main_window
    editor = window.pages["data"]._editor
    buttons = [
        editor._undo_btn,
        editor._redo_btn,
        editor._add_row_btn,
        editor._del_row_btn,
        editor._add_col_btn,
        editor._rename_col_btn,
        editor._drop_col_btn,
        editor._clear_btn,
        editor._prev_btn,
        editor._next_btn,
    ]
    assert len(editor._icon_buttons) == len(buttons)
    for btn in buttons:
        # 纯图标按钮：无文字、有悬浮提示、图标非空
        assert btn.text() == ""
        assert btn.toolTip()
        assert not btn.icon().isNull()
    window.close()


def test_theme_switch_rebuilds_icons(main_window: Any, qapp: Any) -> None:
    """主题切换后图标按新色板重建，仍为非空。."""
    window, theme, *_rest = main_window
    editor = window.pages["data"]._editor
    before = editor._add_row_btn.icon()

    theme.set_dark(True)
    qapp.processEvents()
    after = editor._add_row_btn.icon()
    assert not after.isNull()
    # 深浅主题色值不同，重建后的图标实例已更换
    assert after is not before

    theme.set_dark(False)
    qapp.processEvents()
    assert not editor._add_row_btn.icon().isNull()
    window.close()
