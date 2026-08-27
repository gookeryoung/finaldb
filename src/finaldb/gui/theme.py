"""主题管理器：设计令牌 + QSS 生成（Widgets 版）。

色值沿用 fuscan 风格：GitHub Desktop（浅色）+ Tokyo Night（深色）。
所有色值/字号通过 :class:`ThemeManager` 的方法获取，界面代码禁止硬编码色值。
暗色模式由 ``is_dark`` 状态驱动，切换时 emit ``theme_changed``，
应用层收到后用 :func:`build_qss` 重新生成样式表并整体重设。
"""

from __future__ import annotations

import sys

from PySide2.QtCore import QObject, Signal

__all__ = [
    "RADIUS_LG",
    "RADIUS_MD",
    "RADIUS_SM",
    "SIDEBAR_WIDTH",
    "SPACING_LG",
    "SPACING_MD",
    "SPACING_SM",
    "SPACING_XL",
    "SPACING_XS",
    "ThemeManager",
    "build_qss",
    "detect_font_families",
]

# ----------------------------- 布局常量（8px 基准网格） -----------------------------

SPACING_XS = 4
SPACING_SM = 8
SPACING_MD = 16
SPACING_LG = 24
SPACING_XL = 32

RADIUS_SM = 4
RADIUS_MD = 6
RADIUS_LG = 8

SIDEBAR_WIDTH = 200

# ----------------------------- 双主题色板 -----------------------------

# 浅色：GitHub Desktop
_LIGHT = {
    "primary": "#0366D6",
    "primary_dark": "#035FC4",
    "danger": "#D73A49",
    "warning": "#F0883E",
    "success": "#28A745",
    "text_primary": "#24292E",
    "text_secondary": "#586069",
    "text_on_primary": "#FFFFFF",
    "bg_app": "#F5F6F8",
    "bg_card": "#FFFFFF",
    "bg_hover": "#F6F8FA",
    "bg_selected": "#EDF3FF",
    "border": "#E1E4E8",
    "sidebar": "#FFFFFF",
    "sidebar_hover": "#F6F8FA",
    "row_alt": "#FAFBFC",
    "selection_strong": "#EAF2FF",
}

# 深色：Tokyo Night
_DARK = {
    "primary": "#7AA2F7",
    "primary_dark": "#5C8DF0",
    "danger": "#D73A49",
    "warning": "#F0883E",
    "success": "#28A745",
    "text_primary": "#E0E0EF",
    "text_secondary": "#A0A0B0",
    "text_on_primary": "#FFFFFF",
    "bg_app": "#1A1B26",
    "bg_card": "#1E1F2A",
    "bg_hover": "#2A2B3A",
    "bg_selected": "#2A2B3A",
    "border": "#2E2F3A",
    "sidebar": "#16161E",
    "sidebar_hover": "#22232E",
    "row_alt": "#22232E",
    "selection_strong": "#2A3040",
}


def detect_font_families() -> tuple[str, ...]:
    """按平台返回优先级字体族列表，供 ``QFont.setFamilies()`` 回退使用。

    跨平台最佳实践（Qt 5.13+ ``setFamilies`` 支持自动回退到首个可用字体）：

    - **Windows**：``Microsoft YaHei UI``（Win10+ UI 字体）→
      ``Microsoft YaHei``（Win7 兜底）→ ``Segoe UI`` → ``Arial``
    - **macOS**：``PingFang SC``（苹方）→ ``.AppleSystemUIFont`` →
      ``Helvetica Neue``
    - **Linux**：``Noto Sans CJK SC``（思源黑体）→ ``Source Han Sans SC`` →
      ``Roboto`` → ``DejaVu Sans``

    :return: 字体族优先级列表（首个可用者被采用）
    """
    if sys.platform == "win32":
        return ("Microsoft YaHei UI", "Microsoft YaHei", "Segoe UI", "Arial")
    if sys.platform == "darwin":
        return ("PingFang SC", ".AppleSystemUIFont", "Helvetica Neue", "Arial")
    return ("Noto Sans CJK SC", "Source Han Sans SC", "Roboto", "DejaVu Sans")


class ThemeManager(QObject):
    """主题令牌管理器：色板访问 + 暗色模式与基准字号状态。

    色板为纯函数式访问（按 ``is_dark`` 取浅色/深色组）；
    状态变化时 emit ``theme_changed``，由应用层重建 QSS。
    """

    theme_changed = Signal()

    def __init__(self, parent: QObject | None = None) -> None:
        """初始化主题管理器，默认浅色模式、基准字号 14px。."""
        super().__init__(parent)
        self._dark = False
        self._font_size = 14
        self._min_font_size = 12

    # ----------------------------- 状态 -----------------------------

    def is_dark(self) -> bool:
        """当前是否为暗色模式。."""
        return self._dark

    def set_dark(self, value: bool) -> None:
        """切换暗色模式。."""
        if self._dark != value:
            self._dark = value
            self.theme_changed.emit()  # pyrefly: ignore [missing-attribute]

    def set_base_font_size(self, size: int) -> None:
        """调整基准字号（12~20px 钳位）。."""
        clamped = max(12, min(20, int(size)))
        if self._font_size != clamped:
            self._font_size = clamped
            self.theme_changed.emit()  # pyrefly: ignore [missing-attribute]

    # ----------------------------- 色板 -----------------------------

    def palette(self) -> dict[str, str]:
        """当前主题色板（色名 → 十六进制色值）。."""
        return _DARK if self._dark else _LIGHT

    def color(self, name: str) -> str:
        """按色名取当前主题色值。."""
        return self.palette()[name]

    # ----------------------------- 排版 -----------------------------

    def font_size_body(self) -> int:
        """正文字号（base，默认 14px）。."""
        return self._font_size

    def font_size_caption(self) -> int:
        """caption 字号（base - 2，不低于最小字号）。."""
        return max(self._min_font_size, self._font_size - 2)

    def font_size_small(self) -> int:
        """小字号（base - 1，不低于最小字号）。."""
        return max(self._min_font_size, self._font_size - 1)

    def font_size_heading(self) -> int:
        """标题字号（base + 2，默认 16px）。."""
        return self._font_size + 2

    def font_size_title(self) -> int:
        """大标题字号（base + 4，默认 18px）。."""
        return self._font_size + 4

    def font_size_page_title(self) -> int:
        """页面大标题字号（base + 8，默认 22px）。."""
        return self._font_size + 8

    def font_family(self) -> str:
        """主字体族（平台默认字体族首个可用字体名）。."""
        return detect_font_families()[0]


# ----------------------------- QSS 生成 -----------------------------


def build_qss(theme: ThemeManager) -> str:
    """按当前主题状态生成全局 QSS 样式表。

    Args:
        theme: 主题管理器（色板与字号随暗色模式/字号设置变化）

    Returns:
        可直接传给 ``QApplication.setStyleSheet`` 的 QSS 文本
    """
    c = theme.palette()
    body = theme.font_size_body()
    small = theme.font_size_small()
    caption = theme.font_size_caption()
    family = ", ".join(detect_font_families())
    return f"""
/* ========== 全局基础 ========== */
QWidget {{
    color: {c["text_primary"]};
    font-family: {family};
    font-size: {body}px;
}}
QMainWindow, QDialog {{ background-color: {c["bg_app"]}; }}
QLabel {{ background: transparent; }}
QLabel[caption="true"] {{ color: {c["text_secondary"]}; font-size: {caption}px; }}
QLabel[secondary="true"] {{ color: {c["text_secondary"]}; }}
QLabel[pageTitle="true"] {{ font-size: {theme.font_size_page_title()}px; font-weight: bold; }}
QLabel[heading="true"] {{ font-size: {theme.font_size_heading()}px; font-weight: bold; }}

/* ========== 卡片容器 ========== */
QFrame#card {{
    background-color: {c["bg_card"]};
    border: 1px solid {c["border"]};
    border-radius: {RADIUS_MD}px;
}}
QFrame#sidebarPanel {{
    background-color: {c["sidebar"]};
    border-right: 1px solid {c["border"]};
}}

/* ========== 侧边栏导航项 ========== */
QPushButton#navItem {{
    background: transparent;
    border: none;
    border-left: 3px solid transparent;
    border-radius: 0;
    text-align: left;
    padding: 0 12px 0 16px;
    color: {c["text_secondary"]};
    font-size: {body}px;
    min-height: 40px;
    max-height: 40px;
}}
QPushButton#navItem:hover {{ background-color: {c["sidebar_hover"]}; }}
QPushButton#navItem:checked {{
    background-color: {c["bg_selected"]};
    border-left: 3px solid {c["primary"]};
    color: {c["text_primary"]};
}}
QLabel#navBadge {{
    background-color: {c["bg_selected"]};
    color: {c["text_secondary"]};
    border-radius: 5px;
    font-size: {caption}px;
    font-weight: bold;
}}
QPushButton#navItem:checked QLabel#navBadge {{ background-color: {c["primary"]}; }}

/* ========== 按钮 ========== */
QPushButton {{
    background-color: {c["primary"]};
    color: {c["text_on_primary"]};
    border: none;
    border-radius: {RADIUS_SM}px;
    padding: 6px 16px;
    min-height: 20px;
    font-size: {small}px;
}}
QPushButton:hover {{ background-color: {c["primary_dark"]}; }}
QPushButton:pressed {{ background-color: {c["primary_dark"]}; }}
QPushButton:disabled {{ background-color: {c["border"]}; color: {c["text_secondary"]}; }}
QPushButton[flatButton="true"] {{
    background: transparent;
    color: {c["text_primary"]};
    border: 1px solid {c["border"]};
}}
QPushButton[flatButton="true"]:checked {{
    background-color: {c["primary"]};
    color: {c["text_on_primary"]};
    border: 1px solid {c["primary"]};
}}
QPushButton[modeButton="true"] {{
    background: transparent;
    color: {c["text_primary"]};
    border: 1px solid {c["border"]};
    padding: 4px 12px;
}}
QPushButton[modeButton="true"]:checked {{
    background-color: {c["primary"]};
    color: {c["text_on_primary"]};
    border: 1px solid {c["primary"]};
}}
QPushButton[linkButton="true"] {{
    background: transparent;
    color: {c["text_secondary"]};
    border: none;
    padding: 0 2px;
    font-size: {caption}px;
    min-height: 0;
}}
QPushButton[linkButton="true"]:hover {{ color: {c["danger"]}; }}

/* ========== 输入控件 ========== */
QLineEdit, QComboBox, QSpinBox {{
    background-color: {c["bg_card"]};
    border: 1px solid {c["border"]};
    border-radius: {RADIUS_SM}px;
    padding: 4px 8px;
    min-height: 20px;
    font-size: {small}px;
}}
QLineEdit:focus, QComboBox:focus {{ border: 1px solid {c["primary"]}; }}
QLineEdit:disabled, QComboBox:disabled {{ background-color: {c["bg_hover"]}; color: {c["text_secondary"]}; }}
QComboBox::drop-down {{ border: none; width: 22px; }}
QComboBox QAbstractItemView {{
    background-color: {c["bg_card"]};
    border: 1px solid {c["border"]};
    selection-background-color: {c["bg_selected"]};
    selection-color: {c["text_primary"]};
    font-size: {small}px;
}}

/* ========== 列表 ========== */
QListWidget, QListView, QTreeView {{
    background-color: transparent;
    border: none;
    font-size: {small}px;
}}
QListWidget::item {{ border-radius: {RADIUS_SM}px; }}
QListWidget::item:selected {{ background-color: {c["bg_selected"]}; color: {c["text_primary"]}; }}
QListWidget::item:hover {{ background-color: {c["bg_hover"]}; }}
QListWidget#cardList {{
    background-color: transparent;
    border: none;
}}
QListWidget#cardList::item {{ background: transparent; }}
QScrollBar:vertical {{
    background: transparent;
    width: 8px;
    margin: 0;
}}
QScrollBar::handle:vertical {{
    background: {c["border"]};
    border-radius: 4px;
    min-height: 32px;
}}
QScrollBar::handle:vertical:hover {{ background: {c["text_secondary"]}; }}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
QScrollBar:horizontal {{ background: transparent; height: 8px; margin: 0; }}
QScrollBar::handle:horizontal {{
    background: {c["border"]};
    border-radius: 4px;
    min-width: 32px;
}}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{ width: 0; }}

/* ========== 表格 ========== */
QTableView {{
    background-color: {c["bg_card"]};
    border: 1px solid {c["border"]};
    border-radius: {RADIUS_SM}px;
    gridline-color: {c["border"]};
    font-size: {small}px;
}}
QTableView::item {{ padding: 2px 6px; }}
QTableView::item:alternate {{ background-color: {c["row_alt"]}; }}
QHeaderView::section {{
    background-color: {c["bg_hover"]};
    color: {c["text_secondary"]};
    border: none;
    border-bottom: 1px solid {c["border"]};
    border-right: 1px solid {c["border"]};
    padding: 4px 8px;
    font-size: {caption}px;
}}
QTableCornerButton::section {{ background-color: {c["bg_hover"]}; border: none; }}

/* ========== 文本域 ========== */
QTextEdit, QPlainTextEdit {{
    background-color: {c["bg_card"]};
    border: 1px solid {c["border"]};
    border-radius: {RADIUS_SM}px;
    font-size: {small}px;
    selection-background-color: {c["bg_selected"]};
}}

/* ========== 复选/滑动 ========== */
QCheckBox {{ spacing: {SPACING_SM}px; }}
QCheckBox::indicator {{
    width: 16px;
    height: 16px;
    border-radius: 4px;
    border: 1px solid {c["border"]};
    background: {c["bg_card"]};
}}
QCheckBox::indicator:checked {{
    background-color: {c["primary"]};
    border: 1px solid {c["primary"]};
}}
QSlider::groove:horizontal {{
    height: 4px;
    background: {c["border"]};
    border-radius: 2px;
}}
QSlider::sub-page:horizontal {{ background: {c["primary"]}; border-radius: 2px; }}
QSlider::handle:horizontal {{
    width: 14px;
    height: 14px;
    margin: -5px 0;
    border-radius: 7px;
    background: {c["primary"]};
}}
QSlider::handle:horizontal:hover {{ background: {c["primary_dark"]}; }}

/* ========== 进度条（忙指示） ========== */
QProgressBar {{
    background-color: {c["bg_hover"]};
    border: none;
    border-radius: 4px;
    min-height: 8px;
    max-height: 8px;
    text-align: center;
}}
QProgressBar::chunk {{ background-color: {c["primary"]}; border-radius: 4px; }}

/* ========== 滚动区域 ========== */
QScrollArea {{ border: none; background: transparent; }}
QScrollBar::add-page, QScrollBar::sub-page {{ background: transparent; }}

/* ========== 对话框 ========== */
QMessageBox {{ background-color: {c["bg_card"]}; }}
QInputDialog {{ background-color: {c["bg_card"]}; }}
"""
