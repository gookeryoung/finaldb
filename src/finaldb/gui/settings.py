"""界面设置持久化：QSettings 读写主题暗色模式与基准字号。

ThemeManager 自身保持纯内存状态（便于测试），持久化由应用装配层
（app.create_app）在启动恢复与主题变化时调用本模块完成。
"""

from __future__ import annotations

from PySide2.QtCore import QSettings

__all__ = ["clear_theme_settings", "load_theme_settings", "save_theme_settings"]

_ORG = "finaldb"
_APP = "gui"

# 基准字号范围与默认值（与 ThemeManager 钳位一致）
_FONT_MIN = 12
_FONT_MAX = 20
_FONT_DEFAULT = 14


def load_theme_settings() -> tuple[bool, int]:
    """读取持久化的主题设置。

    :return: (暗色模式, 基准字号)；无记录时返回默认 (False, 14)，
        字号越界时钳位到 12~20
    """
    settings = QSettings(_ORG, _APP)
    dark = bool(settings.value("theme/dark", False, type=bool))
    size = int(settings.value("theme/fontSize", _FONT_DEFAULT, type=int))
    return dark, max(_FONT_MIN, min(_FONT_MAX, size))


def save_theme_settings(dark: bool, font_size: int) -> None:
    """保存主题设置并立即落盘。."""
    settings = QSettings(_ORG, _APP)
    settings.setValue("theme/dark", dark)
    settings.setValue("theme/fontSize", font_size)
    settings.sync()


def clear_theme_settings() -> None:
    """清空持久化设置（测试隔离用）。."""
    settings = QSettings(_ORG, _APP)
    settings.clear()
    settings.sync()
