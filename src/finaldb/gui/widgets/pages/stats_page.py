"""统计页：工作区表分布概览与条形图。."""

from __future__ import annotations

from PySide2.QtCore import Qt
from PySide2.QtGui import QShowEvent
from PySide2.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from finaldb.gui.controllers.stats_controller import StatsController
from finaldb.gui.controllers.workspace_controller import WorkspaceController
from finaldb.gui.theme import SPACING_MD, SPACING_SM, ThemeManager
from finaldb.gui.widgets.common import caption_label, card, page_title, workspace_hint

__all__ = ["StatsPage"]

# 条形高度与最小宽度（像素）
_BAR_HEIGHT = 14
_BAR_MIN_WIDTH = 4


class StatsPage(QWidget):
    """统计页：摘要 + 表行数分布条形图（滚动容器）。."""

    def __init__(
        self,
        theme: ThemeManager,
        workspace_ctrl: WorkspaceController,
        stats_ctrl: StatsController,
        parent: QWidget | None = None,
    ) -> None:
        """初始化页面并装配控制器信号。

        Args:
            theme: 主题管理器
            workspace_ctrl: 工作区控制器
            stats_ctrl: 统计控制器
            parent: 父部件
        """
        super().__init__(parent)
        self._theme = theme
        self._ws = workspace_ctrl
        self._stats = stats_ctrl
        self._bars: list[QWidget] = []

        root = QVBoxLayout(self)
        root.setContentsMargins(SPACING_MD, SPACING_MD, SPACING_MD, SPACING_MD)
        root.setSpacing(SPACING_MD)

        # ---------- 顶部工具栏 ----------
        bar = QHBoxLayout()
        bar.setSpacing(SPACING_SM)
        bar.addWidget(page_title("统计"))
        bar.addWidget(workspace_hint(theme, workspace_ctrl, "未选择工作区（请先在数据源页选择）"), stretch=1)
        refresh_btn = QPushButton("刷新")
        refresh_btn.clicked.connect(lambda: self._stats.load_stats(self._ws.current_workspace_path()))
        bar.addWidget(refresh_btn)
        root.addLayout(bar)

        # ---------- 摘要 ----------
        self._summary = QLabel("")
        self._summary.setObjectName("statsSummary")
        root.addWidget(self._summary)

        # ---------- 表分布条形图 ----------
        chart_card = card()
        card_layout = QVBoxLayout(chart_card)
        card_layout.setContentsMargins(12, 12, 12, 12)
        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._rows_host = QWidget()
        self._rows_layout = QVBoxLayout(self._rows_host)
        self._rows_layout.setContentsMargins(0, 0, 0, 0)
        self._rows_layout.setSpacing(SPACING_SM)
        self._rows_layout.addStretch(1)
        self._scroll.setWidget(self._rows_host)
        card_layout.addWidget(self._scroll)
        root.addWidget(chart_card, stretch=1)

        # ---------- 信号装配 ----------
        self._stats.stats_changed.connect(self._refresh)  # pyrefly: ignore [missing-attribute]
        self._ws.current_changed.connect(  # pyrefly: ignore [missing-attribute]
            lambda: self._stats.load_stats(self._ws.current_workspace_path())
        )
        self._theme.theme_changed.connect(self._restyle_bars)  # pyrefly: ignore [missing-attribute]

        self._stats.load_stats(self._ws.current_workspace_path())
        self._refresh()

    # ----------------------------- 内部 -----------------------------

    def showEvent(self, event: QShowEvent) -> None:
        """页面可见时刷新统计（对齐 QML onVisibleChanged）。."""
        super().showEvent(event)
        if self._ws.current_workspace_path():
            self._stats.load_stats(self._ws.current_workspace_path())

    def _refresh(self) -> None:
        """统计变化：刷新摘要并重建条形图行。."""
        self._summary.setText(self._stats.summary_text())
        # 清空旧行（保留尾部弹簧）
        while self._rows_layout.count() > 1:
            item = self._rows_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        self._bars = []

        model = self._stats.stats_model()
        for row in range(model.rowCount()):
            index = model.index(row, 0)
            name = str(model.data(index, Qt.UserRole + 1) or "")
            rows = model.data(index, Qt.UserRole + 2)
            ratio = float(model.data(index, Qt.UserRole + 5) or 0.0)
            self._rows_layout.insertLayout(self._rows_layout.count() - 1, self._build_bar_row(name, ratio, rows))
        self._restyle_bars()

    def _build_bar_row(self, name: str, ratio: float, rows: object) -> QHBoxLayout:
        """构建单行条形图：名称 | 比例条 | 行数。."""
        row = QHBoxLayout()
        row.setSpacing(SPACING_SM)
        name_label = QLabel(name)
        name_label.setFixedWidth(140)
        bar_holder = QWidget()
        holder_layout = QHBoxLayout(bar_holder)
        holder_layout.setContentsMargins(0, 0, 0, 0)
        holder_layout.setSpacing(0)
        bar = QWidget()
        bar.setFixedHeight(_BAR_HEIGHT)
        bar.setMinimumWidth(_BAR_MIN_WIDTH)
        spacer = QWidget()
        holder_layout.addWidget(bar)
        holder_layout.addWidget(spacer)
        # 以 stretch 比例实现条宽随行数占比与窗口宽度自适应
        filled = max(1, int(ratio * 1000))
        holder_layout.setStretch(0, filled)
        holder_layout.setStretch(1, max(0, 1000 - filled))
        self._bars.append(bar)
        rows_label = caption_label(f"{rows} 行")
        row.addWidget(name_label)
        row.addWidget(bar_holder, stretch=1)
        row.addWidget(rows_label)
        return row

    def _restyle_bars(self) -> None:
        """按当前主题刷新条形颜色。."""
        color = self._theme.color("primary")
        for bar in self._bars:
            bar.setStyleSheet(f"background-color: {color}; border-radius: 4px;")
