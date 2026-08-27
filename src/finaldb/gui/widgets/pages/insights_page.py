"""统计与版本页：分段按钮切换统计 / 版本历史两个子面板。."""

from __future__ import annotations

from PySide2.QtCore import Qt
from PySide2.QtWidgets import QButtonGroup, QHBoxLayout, QPushButton, QStackedWidget, QVBoxLayout, QWidget

from finaldb.gui.controllers.history_controller import HistoryController
from finaldb.gui.controllers.stats_controller import StatsController
from finaldb.gui.controllers.workspace_controller import WorkspaceController
from finaldb.gui.theme import SPACING_MD, SPACING_SM, ThemeManager
from finaldb.gui.widgets.common import page_title, workspace_hint
from finaldb.gui.widgets.pages.history_page import HistoryPage
from finaldb.gui.widgets.pages.stats_page import StatsPage

__all__ = ["InsightsPage"]

# 分段按钮文本（与子面板顺序一致）
_SEG_TITLES = ("统计", "版本历史")


class InsightsPage(QWidget):
    """统计与版本页：顶部分段按钮 + 子面板栈（统计 | 版本历史）。."""

    def __init__(
        self,
        theme: ThemeManager,
        workspace_ctrl: WorkspaceController,
        stats_ctrl: StatsController,
        history_ctrl: HistoryController,
        parent: QWidget | None = None,
    ) -> None:
        """初始化页面并装配子面板。

        Args:
            theme: 主题管理器
            workspace_ctrl: 工作区控制器
            stats_ctrl: 统计控制器
            history_ctrl: 历史控制器
            parent: 父部件
        """
        super().__init__(parent)
        self._theme = theme
        self._ws = workspace_ctrl

        root = QVBoxLayout(self)
        root.setContentsMargins(SPACING_MD, SPACING_MD, SPACING_MD, SPACING_MD)
        root.setSpacing(SPACING_MD)

        # ---------- 顶部工具栏：标题 + 工作区提示 + 分段按钮 ----------
        bar = QHBoxLayout()
        bar.setSpacing(SPACING_SM)
        bar.addWidget(page_title("统计与版本"))
        bar.addWidget(workspace_hint(theme, workspace_ctrl, "未选择工作区（请先在数据页选择）"), stretch=1)
        self._seg_group = QButtonGroup(self)
        self._seg_group.setExclusive(True)
        self._seg_buttons: list[QPushButton] = []
        for index, title in enumerate(_SEG_TITLES):
            seg_btn = QPushButton(title)
            seg_btn.setProperty("modeButton", True)
            seg_btn.setCheckable(True)
            seg_btn.setChecked(index == 0)
            seg_btn.setCursor(Qt.PointingHandCursor)
            self._seg_group.addButton(seg_btn, index)
            seg_btn.clicked.connect(lambda _=False, idx=index: self._on_seg_clicked(idx))
            self._seg_buttons.append(seg_btn)
            bar.addWidget(seg_btn)
        root.addLayout(bar)

        # ---------- 子面板栈：统计 | 版本历史 ----------
        self._stack = QStackedWidget()
        self._stats_pane = StatsPage(theme, workspace_ctrl, stats_ctrl)
        self._history_pane = HistoryPage(theme, workspace_ctrl, history_ctrl)
        self._stack.addWidget(self._stats_pane)
        self._stack.addWidget(self._history_pane)
        root.addWidget(self._stack, stretch=1)

    # ----------------------------- 内部 -----------------------------

    def _on_seg_clicked(self, index: int) -> None:
        """切换子面板（触发子面板 showEvent 重载数据）。."""
        self._stack.setCurrentIndex(index)
