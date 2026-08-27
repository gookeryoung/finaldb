"""矢量图标工厂与编辑面板按钮图标测试。."""

from __future__ import annotations

from typing import Any

import pytest

from finaldb.gui.widgets.icons import ICON_NAMES, build_icon

pytestmark = pytest.mark.gui


def test_all_icons_non_null(qapp: Any) -> None:
    """全部注册图标均可绘制出非空 pixmap。."""
    for name in ICON_NAMES:
        icon = build_icon(name, "#0366D6")
        assert not icon.isNull()
        assert not icon.pixmap(24, 24).isNull()


def test_unknown_icon_raises(qapp: Any) -> None:
    """未注册图标名：抛 ValueError 且提示含原名。."""
    with pytest.raises(ValueError, match="未知图标名称: nope"):
        build_icon("nope", "#000000")


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
