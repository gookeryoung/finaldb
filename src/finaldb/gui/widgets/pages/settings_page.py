"""设置页：外观（暗色模式/字号）与数据（工作区根目录）偏好。."""

from __future__ import annotations

from PySide2.QtCore import Qt
from PySide2.QtWidgets import (
    QCheckBox,
    QHBoxLayout,
    QLabel,
    QScrollArea,
    QSlider,
    QVBoxLayout,
    QWidget,
)

from finaldb.gui.controllers.about_controller import AboutController
from finaldb.gui.controllers.workspace_controller import WorkspaceController
from finaldb.gui.theme import SPACING_MD, SPACING_SM, ThemeManager
from finaldb.gui.widgets.common import caption_label, card, page_title, secondary_label

__all__ = ["SettingsPage"]


class SettingsPage(QWidget):
    """设置页：外观/数据/版本三张设置卡。."""

    def __init__(
        self,
        theme: ThemeManager,
        workspace_ctrl: WorkspaceController,
        about_ctrl: AboutController,
        parent: QWidget | None = None,
    ) -> None:
        """初始化页面。

        Args:
            theme: 主题管理器
            workspace_ctrl: 工作区控制器（读取工作区根目录）
            about_ctrl: 关于控制器（读取版本号）
            parent: 父部件
        """
        super().__init__(parent)
        self._theme = theme
        self._ws = workspace_ctrl
        self._about = about_ctrl

        root = QVBoxLayout(self)
        root.setContentsMargins(SPACING_MD, SPACING_MD, SPACING_MD, SPACING_MD)
        root.setSpacing(SPACING_MD)
        root.addWidget(page_title("设置"))

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(SPACING_MD)
        content_layout.addWidget(self._build_appearance_card())
        content_layout.addWidget(self._build_data_card())
        content_layout.addWidget(self._build_version_card())
        content_layout.addStretch(1)
        scroll.setWidget(content)
        root.addWidget(scroll, stretch=1)

        self._theme.theme_changed.connect(self._sync_controls)  # pyrefly: ignore [missing-attribute]

    # ----------------------------- 卡片构建 -----------------------------

    def _build_appearance_card(self) -> QWidget:
        """构建外观卡：暗色模式开关 + 字号滑杆。."""
        appearance = card()
        layout = QVBoxLayout(appearance)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(SPACING_SM)
        heading = QLabel("外观")
        heading.setProperty("heading", True)
        layout.addWidget(heading)

        dark_row = QHBoxLayout()
        dark_row.addWidget(QLabel("暗色模式"), stretch=1)
        self._dark_check = QCheckBox()
        self._dark_check.setObjectName("darkSwitch")
        self._dark_check.setChecked(self._theme.is_dark())
        self._dark_check.toggled.connect(self._theme.set_dark)
        dark_row.addWidget(self._dark_check)
        layout.addLayout(dark_row)

        font_row = QHBoxLayout()
        font_row.setSpacing(SPACING_SM)
        font_row.addWidget(QLabel("界面字号"))
        self._font_label = caption_label(f"{self._theme.font_size_body()} px")
        font_row.addWidget(self._font_label)
        self._font_slider = QSlider(Qt.Horizontal)
        self._font_slider.setObjectName("fontSlider")
        self._font_slider.setRange(12, 20)
        self._font_slider.setValue(self._theme.font_size_body())
        self._font_slider.valueChanged.connect(self._theme.set_base_font_size)
        font_row.addWidget(self._font_slider, stretch=1)
        layout.addLayout(font_row)
        return appearance

    def _build_data_card(self) -> QWidget:
        """构建数据卡：工作区根目录展示。."""
        data = card()
        layout = QVBoxLayout(data)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(SPACING_SM)
        heading = QLabel("数据")
        heading.setProperty("heading", True)
        layout.addWidget(heading)
        self._root_label = secondary_label(f"工作区根目录: {self._ws.workspace_root()}")
        layout.addWidget(self._root_label)
        return data

    def _build_version_card(self) -> QWidget:
        """构建版本卡：版本号摘要。."""
        version = card()
        layout = QVBoxLayout(version)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(SPACING_SM)
        heading = QLabel("版本")
        heading.setProperty("heading", True)
        layout.addWidget(heading)
        layout.addWidget(secondary_label(f"finaldb {self._about.version()}，详细依赖清单见「关于」页"))
        return version

    # ----------------------------- 内部 -----------------------------

    def _sync_controls(self) -> None:
        """主题变化（可能来自侧边栏开关）：回读刷新本页控件状态。."""
        self._dark_check.blockSignals(True)
        self._dark_check.setChecked(self._theme.is_dark())
        self._dark_check.blockSignals(False)
        self._font_slider.blockSignals(True)
        self._font_slider.setValue(self._theme.font_size_body())
        self._font_slider.blockSignals(False)
        self._font_label.setText(f"{self._theme.font_size_body()} px")
