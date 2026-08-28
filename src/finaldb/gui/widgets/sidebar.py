"""侧边栏导航：Logo + 主导航/辅助导航（SVG 图标）+ 暗色模式开关。."""

from __future__ import annotations

from PySide2.QtCore import Qt, Signal
from PySide2.QtWidgets import QButtonGroup, QCheckBox, QFrame, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from finaldb.gui.theme import SIDEBAR_WIDTH, SPACING_SM, ThemeManager
from finaldb.gui.widgets.icons import build_icon

__all__ = ["NavButton", "Sidebar"]

# 导航项定义：(page_id, 图标名, 标签)
_MAIN_NAV = [
    ("data", "database", "数据"),
    ("stats", "stats", "统计"),
]
_AUX_NAV = [
    ("settings", "settings", "设置"),
    ("about", "about", "关于"),
]

# 导航图标尺寸（逻辑像素）
_NAV_ICON = 18


class NavButton(QPushButton):
    """侧边栏导航项按钮：SVG 图标 + 文本，选中态左侧强调竖条。

    竖条/背景由全局 QSS（``#navItem``）驱动；图标颜色随
    选中态与主题在代码中刷新（选中取主色，未选中取次级文字色）。
    """

    def __init__(self, page_id: str, icon_name: str, text: str, theme: ThemeManager) -> None:
        """初始化导航按钮。

        Args:
            page_id: 页面标识（data/stats/...）
            icon_name: 图标名（须在 ``ICON_NAMES`` 内）
            text: 导航文本
            theme: 主题管理器
        """
        super().__init__()
        self.page_id = page_id
        self._icon_name = icon_name
        self._theme = theme
        self.setObjectName("navItem")
        self.setCheckable(True)
        self.setCursor(Qt.PointingHandCursor)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 0, 12, 0)
        layout.setSpacing(10)
        self._badge = QLabel(self)
        self._badge.setFixedSize(_NAV_ICON, _NAV_ICON)
        self._badge.setAlignment(Qt.AlignCenter)
        self._label = QLabel(text, self)
        layout.addWidget(self._badge)
        layout.addWidget(self._label, stretch=1)
        self.toggled.connect(self._refresh_badge)
        theme.theme_changed.connect(self._refresh_badge)  # pyrefly: ignore [missing-attribute]
        self._refresh_badge()

    def _refresh_badge(self) -> None:
        """按选中态与主题刷新图标颜色（选中主色 / 未选中次级色）。."""
        palette = self._theme.palette()
        color = palette["primary"] if self.isChecked() else palette["text_secondary"]
        self._badge.setPixmap(build_icon(self._icon_name, color).pixmap(_NAV_ICON, _NAV_ICON))


class Sidebar(QFrame):
    """侧边栏：Logo 区 + 顶部主导航 + 底部辅助导航 + 暗色模式开关。."""

    page_requested = Signal(str)

    def __init__(self, theme: ThemeManager, parent: QWidget | None = None) -> None:
        """初始化侧边栏并构建导航。."""
        super().__init__(parent)
        self._theme = theme
        self.setObjectName("sidebarPanel")
        self.setFixedWidth(SIDEBAR_WIDTH)
        self._buttons: dict[str, NavButton] = {}
        # 互斥按钮组：切换选中时自动取消其余按钮，避免激活态残留
        self._group = QButtonGroup(self)
        self._group.setExclusive(True)

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        root.addWidget(self._build_logo())

        for page_id, icon_name, text in _MAIN_NAV:
            root.addWidget(self._make_nav(page_id, icon_name, text))

        root.addStretch(1)

        for page_id, icon_name, text in _AUX_NAV:
            root.addWidget(self._make_nav(page_id, icon_name, text))

        root.addWidget(self._build_dark_row())
        self._buttons["data"].setChecked(True)

    # ----------------------------- 对外 API -----------------------------

    def set_current_page(self, page_id: str) -> None:
        """同步导航选中态（互斥组自动清除其余按钮，由主窗口调用）。."""
        button = self._buttons.get(page_id)
        if button is not None:
            button.setChecked(True)

    # ----------------------------- 内部 -----------------------------

    def _make_nav(self, page_id: str, icon_name: str, text: str) -> NavButton:
        """构造一个导航按钮并接入点击信号。."""
        button = NavButton(page_id, icon_name, text, self._theme)
        self._buttons[page_id] = button
        self._group.addButton(button)
        button.clicked.connect(lambda: self.page_requested.emit(page_id))  # pyrefly: ignore [missing-attribute]
        return button

    def _build_logo(self) -> QWidget:
        """构建 Logo 区：主色图标块（database 图标）+ finaldb。."""
        row = QWidget(self)
        row.setFixedHeight(64)
        layout = QHBoxLayout(row)
        layout.setContentsMargins(20, 0, 16, 0)
        layout.setSpacing(10)
        badge = QLabel(row)
        badge.setFixedSize(28, 28)
        badge.setAlignment(Qt.AlignCenter)
        title = QLabel("finaldb", row)
        title_font = title.font()
        title_font.setPixelSize(15)
        title_font.setBold(True)
        title.setFont(title_font)
        layout.addWidget(badge)
        layout.addWidget(title)
        layout.addStretch(1)
        self._theme.theme_changed.connect(lambda: self._style_logo(badge))  # pyrefly: ignore [missing-attribute]
        self._style_logo(badge)
        return row

    def _style_logo(self, badge: QLabel) -> None:
        """按当前主题刷新 Logo 色块样式与图标。."""
        palette = self._theme.palette()
        badge.setStyleSheet(f"background-color: {palette['primary']}; border-radius: 6px;")
        badge.setPixmap(build_icon("database", palette["text_on_primary"]).pixmap(18, 18))

    def _build_dark_row(self) -> QWidget:
        """构建暗色模式切换行（moon/sun 图标随主题切换 + 复选框）。."""
        row = QFrame(self)
        row.setObjectName("darkRow")
        layout = QHBoxLayout(row)
        layout.setContentsMargins(14, 8, 14, 16)
        layout.setSpacing(SPACING_SM)
        icon = QLabel(row)
        icon.setFixedSize(16, 16)
        icon.setAlignment(Qt.AlignCenter)
        check = QCheckBox("暗色模式", row)
        check.setChecked(self._theme.is_dark())
        check.toggled.connect(self._theme.set_dark)
        layout.addWidget(icon)
        layout.addWidget(check, stretch=1)
        self._theme.theme_changed.connect(lambda: self._style_dark_row(row, icon))  # pyrefly: ignore [missing-attribute]
        self._style_dark_row(row, icon)
        return row

    def _style_dark_row(self, row: QFrame, icon: QLabel) -> None:
        """按当前主题刷新暗色切换行样式与 moon/sun 图标。"""
        palette = self._theme.palette()
        row.setStyleSheet(
            f"QFrame#darkRow {{ background-color: {palette['sidebar_hover'] if self._theme.is_dark() else palette['bg_app']};"
            f" border: 1px solid {palette['border']}; border-radius: 8px; }}"
        )
        name = "moon" if self._theme.is_dark() else "sun"
        icon.setPixmap(build_icon(name, palette["text_secondary"]).pixmap(16, 16))
