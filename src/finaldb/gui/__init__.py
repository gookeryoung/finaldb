"""GUI 模块门面：仅做 re-export，不含业务实现。."""

from __future__ import annotations

from finaldb.gui.theme import ThemeController, detect_font_families

__all__ = ["ThemeController", "detect_font_families"]
