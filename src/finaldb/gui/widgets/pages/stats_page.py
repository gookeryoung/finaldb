"""统计页：工作区概览 + 表行数分布条形图 + 单表列级统计表。."""

from __future__ import annotations

from PySide2.QtCore import Qt
from PySide2.QtGui import QFontMetrics, QShowEvent
from PySide2.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QScrollArea,
    QStackedWidget,
    QTableView,
    QVBoxLayout,
    QWidget,
)

from finaldb.gui.controllers.stats_controller import StatsController
from finaldb.gui.controllers.workspace_controller import WorkspaceController
from finaldb.gui.theme import SPACING_MD, SPACING_SM, ThemeManager
from finaldb.gui.widgets.common import caption_label, card, page_title, workspace_hint
from finaldb.gui.widgets.icons import build_icon

__all__ = ["StatsPage"]

# 条形行各列宽度（逻辑像素）：名称标签 / 行数标签
_NAME_WIDTH = 120
_ROWS_WIDTH = 56
# 名称省略占位
_ELLIPSIS = "..."


class StatsPage(QWidget):
    """统计页：概览摘要 + 左侧表分布条形图 + 右侧列统计表。."""

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
        self._current_table = ""

        root = QVBoxLayout(self)
        root.setContentsMargins(SPACING_MD, SPACING_MD, SPACING_MD, SPACING_MD)
        root.setSpacing(SPACING_MD)

        # ---------- 顶部工具栏 ----------
        bar = QHBoxLayout()
        bar.setSpacing(SPACING_SM)
        bar.addWidget(page_title("统计"))
        bar.addWidget(workspace_hint(theme, workspace_ctrl, "未选择工作区（请先在数据页选择）"), stretch=1)
        refresh_btn = QPushButton("刷新")
        refresh_btn.clicked.connect(self._reload_all)
        self._refresh_btn = refresh_btn
        bar.addWidget(refresh_btn)
        root.addLayout(bar)

        # ---------- 摘要 ----------
        self._summary = QLabel("")
        self._summary.setObjectName("statsSummary")
        self._summary.setWordWrap(True)
        root.addWidget(self._summary)

        # ---------- 主体两栏 ----------
        body = QHBoxLayout()
        body.setSpacing(SPACING_MD)

        # 左：表行数分布条形图
        left = card()
        left.setFixedWidth(340)
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(SPACING_SM, SPACING_SM, SPACING_SM, SPACING_SM)
        left_layout.setSpacing(SPACING_SM)
        left_layout.addWidget(caption_label("表行数分布"))
        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._rows_host = QWidget()
        self._rows_layout = QVBoxLayout(self._rows_host)
        self._rows_layout.setContentsMargins(0, 0, 0, 0)
        self._rows_layout.setSpacing(SPACING_SM)
        self._rows_layout.addStretch(1)
        self._scroll.setWidget(self._rows_host)
        left_layout.addWidget(self._scroll, stretch=1)
        body.addWidget(left)

        # 右：表选择 + 列统计表
        right = card()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(SPACING_SM, SPACING_SM, SPACING_SM, SPACING_SM)
        right_layout.setSpacing(SPACING_SM)

        table_row = QHBoxLayout()
        table_row.setSpacing(SPACING_SM)
        table_row.addWidget(caption_label("数据表"))
        self._table_combo = QComboBox()
        self._table_combo.setObjectName("statsTableCombo")
        self._table_combo.activated.connect(self._on_table_activated)
        table_row.addWidget(self._table_combo, stretch=1)
        right_layout.addLayout(table_row)

        self._stat_view = QTableView()
        self._stat_view.setObjectName("statsView")
        self._stat_view.setModel(self._stats.table_stats_model())
        self._stat_view.setEditTriggers(QTableView.NoEditTriggers)
        self._stat_view.setAlternatingRowColors(True)
        self._stat_view.verticalHeader().setVisible(False)
        header = self._stat_view.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeToContents)
        header.setMinimumSectionSize(72)
        header.setStretchLastSection(True)

        self._stat_empty = caption_label("选择数据表后查看列统计")
        self._stat_empty.setAlignment(Qt.AlignCenter)
        self._stat_empty.setWordWrap(True)

        # 表格与空态互斥占位（同一栈位切换，避免同时占位挤压）
        self._stat_stack = QStackedWidget()
        self._stat_stack.addWidget(self._stat_view)
        self._stat_stack.addWidget(self._stat_empty)
        right_layout.addWidget(self._stat_stack, stretch=1)

        body.addWidget(right, stretch=1)

        root.addLayout(body, stretch=1)

        # ---------- 信号装配 ----------
        self._stats.stats_changed.connect(self._refresh)  # pyrefly: ignore [missing-attribute]
        self._stats.table_stats_changed.connect(self._update_stat_state)  # pyrefly: ignore [missing-attribute]
        self._ws.current_changed.connect(self._on_workspace_changed)  # pyrefly: ignore [missing-attribute]
        self._theme.theme_changed.connect(self._restyle_bars)  # pyrefly: ignore [missing-attribute]
        self._theme.theme_changed.connect(self._apply_icons)  # pyrefly: ignore [missing-attribute]
        self._apply_icons()

        self._stats.load_stats(self._ws.current_workspace_path())
        self._refresh()

    def _apply_icons(self) -> None:
        """按当前主题为刷新按钮重建图标（secondary 描边取正文色）。."""
        self._refresh_btn.setIcon(build_icon("refresh", self._theme.color("text_primary")))

    # ----------------------------- 内部 -----------------------------

    def showEvent(self, event: QShowEvent) -> None:
        """页面可见时刷新统计。."""
        super().showEvent(event)
        if self._ws.current_workspace_path():
            self._reload_all()

    def _reload_all(self) -> None:
        """重载概览与当前表列统计。."""
        path = self._ws.current_workspace_path()
        self._stats.load_stats(path)
        self._refresh()
        self._stats.load_table_stats(path, self._current_table)

    def _on_workspace_changed(self) -> None:
        """工作区切换：重置表选择并重载统计。."""
        self._current_table = ""
        self._stats.load_stats(self._ws.current_workspace_path())
        self._stats.load_table_stats(self._ws.current_workspace_path(), "")

    def _on_table_activated(self, index: int) -> None:
        """选择数据表：加载该表列统计。."""
        self._current_table = self._table_combo.itemText(index)
        self._stats.load_table_stats(self._ws.current_workspace_path(), self._current_table)

    def _refresh(self) -> None:
        """统计变化：刷新摘要、表下拉并重建条形图行。."""
        self._summary.setText(self._stats.summary_text())
        self._reload_table_combo()
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
        self._update_stat_state()

    def _reload_table_combo(self) -> None:
        """按统计模型刷新表下拉（保持当前选择有效）。."""
        names = self._stats.table_names()
        self._table_combo.blockSignals(True)
        self._table_combo.clear()
        self._table_combo.addItems(names)
        if self._current_table in names:
            self._table_combo.setCurrentText(self._current_table)
        else:
            self._current_table = ""
        self._table_combo.blockSignals(False)

    def _update_stat_state(self) -> None:
        """按模型行数切换统计表与空态（栈互斥占位）。."""
        has_stats = self._stats.table_stats_model().rowCount() > 0
        self._stat_stack.setCurrentWidget(self._stat_view if has_stats else self._stat_empty)
        if not has_stats:
            self._stat_empty.setText(
                "选择数据表后查看列统计" if self._table_combo.count() > 0 else "当前工作区暂无数据表"
            )

    def _build_bar_row(self, name: str, ratio: float, rows: object) -> QHBoxLayout:
        """构建单行条形图：名称（省略）| 比例条 | 行数（右对齐）。."""
        row = QHBoxLayout()
        row.setSpacing(SPACING_SM)
        # 名称超宽时中部省略，避免挤压条形与行数
        name_label = QLabel(self._elide_middle(name, _NAME_WIDTH))
        name_label.setFixedWidth(_NAME_WIDTH)
        name_label.setToolTip(name)
        bar_holder = QWidget()
        holder_layout = QHBoxLayout(bar_holder)
        holder_layout.setContentsMargins(0, 0, 0, 0)
        holder_layout.setSpacing(0)
        bar = QWidget()
        bar.setFixedHeight(14)
        spacer = QWidget()
        holder_layout.addWidget(bar)
        holder_layout.addWidget(spacer)
        # stretch 比例控制条宽占比（fill : 1000-fill），随容器宽度自适应
        filled = max(1, int(ratio * 1000))
        holder_layout.setStretch(0, filled)
        holder_layout.setStretch(1, max(0, 1000 - filled))
        self._bars.append(bar)
        rows_label = caption_label(f"{rows} 行")
        rows_label.setFixedWidth(_ROWS_WIDTH)
        rows_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        row.addWidget(name_label)
        row.addWidget(bar_holder, stretch=1)
        row.addWidget(rows_label)
        return row

    @staticmethod
    def _elide_middle(text: str, width: int) -> str:
        """按像素宽中部省略文本（保留首尾，中间以 ... 替代）。."""
        metrics = QFontMetrics(QLabel().font())
        if metrics.horizontalAdvance(text) <= width:
            return text
        keep = max(1, (len(text) - 1) // 2)
        while keep > 1 and metrics.horizontalAdvance(text[:keep] + _ELLIPSIS + text[-keep:]) > width:
            keep -= 1
        return text[:keep] + _ELLIPSIS + text[-keep:]

    def _restyle_bars(self) -> None:
        """按当前主题刷新条形颜色。."""
        color = self._theme.color("primary")
        for bar in self._bars:
            bar.setStyleSheet(f"background-color: {color}; border-radius: 4px;")
