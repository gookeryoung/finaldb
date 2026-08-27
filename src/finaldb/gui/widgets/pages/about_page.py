"""关于页：版本信息与开源许可。."""

from __future__ import annotations

from PySide2.QtCore import Qt
from PySide2.QtGui import QFont
from PySide2.QtWidgets import QGridLayout, QHBoxLayout, QLabel, QVBoxLayout, QWidget

from finaldb.gui.controllers.about_controller import AboutController
from finaldb.gui.theme import SPACING_MD, SPACING_SM, ThemeManager
from finaldb.gui.widgets.common import caption_label, card, page_title, secondary_label

__all__ = ["AboutPage"]


class AboutPage(QWidget):
    """关于页：产品信息卡 + 运行环境卡。."""

    def __init__(self, theme: ThemeManager, about_ctrl: AboutController, parent: QWidget | None = None) -> None:
        """初始化页面。

        Args:
            theme: 主题管理器
            about_ctrl: 关于控制器（版本与环境信息）
            parent: 父部件
        """
        super().__init__(parent)
        self._theme = theme
        self._about = about_ctrl

        root = QVBoxLayout(self)
        root.setContentsMargins(SPACING_MD, SPACING_MD, SPACING_MD, SPACING_MD)
        root.setSpacing(SPACING_MD)
        root.addWidget(page_title("关于"))

        # ---------- 产品信息卡 ----------
        product = card()
        product.setFixedHeight(152)
        product_layout = QVBoxLayout(product)
        product_layout.setContentsMargins(16, 16, 16, 16)
        product_layout.setSpacing(SPACING_SM)

        head = QHBoxLayout()
        head.setSpacing(SPACING_SM)
        head.setAlignment(Qt.AlignHCenter)
        self._badge = QLabel("库")
        self._badge.setFixedSize(48, 48)
        self._badge.setAlignment(Qt.AlignCenter)
        badge_font = QFont()
        badge_font.setPixelSize(22)
        badge_font.setBold(True)
        self._badge.setFont(badge_font)
        head.addWidget(self._badge)
        title = QLabel("finaldb")
        title_font = QFont()
        title_font.setPixelSize(theme.font_size_title())
        title_font.setBold(True)
        title.setFont(title_font)
        head.addWidget(title)
        head.addWidget(secondary_label(f"v{about_ctrl.version()}"))
        product_layout.addLayout(head)

        desc = secondary_label("终极数据库管理软件：导入、整理、合并去重与快照级版本控制")
        desc.setAlignment(Qt.AlignHCenter)
        product_layout.addWidget(desc)
        license_line = caption_label(f"开源许可: {about_ctrl.license_text()}")
        license_line.setAlignment(Qt.AlignHCenter)
        product_layout.addWidget(license_line)
        product_layout.addStretch(1)
        root.addWidget(product)

        # ---------- 运行环境卡 ----------
        env = card()
        env_layout = QVBoxLayout(env)
        env_layout.setContentsMargins(16, 16, 16, 16)
        env_layout.setSpacing(SPACING_SM)
        heading = QLabel("运行环境")
        heading.setProperty("heading", True)
        env_layout.addWidget(heading)

        grid = QGridLayout()
        grid.setHorizontalSpacing(SPACING_MD)
        grid.setVerticalSpacing(SPACING_SM)
        entries = [
            ("Python", about_ctrl.python_version()),
            ("Qt", about_ctrl.qt_version()),
            ("PySide2", about_ctrl.pyside2_version()),
            ("dulwich", about_ctrl.dulwich_version()),
        ]
        for row, (name, value) in enumerate(entries):
            grid.addWidget(secondary_label(name), row, 0)
            grid.addWidget(QLabel(value), row, 1)
        env_layout.addLayout(grid)

        env_layout.addStretch(1)
        offline = caption_label("界面与引擎均为离线运行，数据存储于本地工作区，不上传任何远端。")
        offline.setWordWrap(True)
        env_layout.addWidget(offline)
        root.addWidget(env, stretch=1)

        # ---------- 主题联动 ----------
        self._theme.theme_changed.connect(self._style_badge)  # pyrefly: ignore [missing-attribute]
        self._style_badge()

    # ----------------------------- 内部 -----------------------------

    def _style_badge(self) -> None:
        """按当前主题刷新「库」色块配色。."""
        palette = self._theme.palette()
        self._badge.setStyleSheet(
            f"background-color: {palette['primary']}; color: {palette['text_on_primary']};"
            f" border-radius: 8px; font-weight: bold;"
        )
