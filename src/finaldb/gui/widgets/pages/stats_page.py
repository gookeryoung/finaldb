"""统计页：指标卡概览 + 行数分布 + 类型分布/空值 TOP + 单表列统计表。."""

from __future__ import annotations

from PySide2.QtCore import Qt
from PySide2.QtGui import QFontMetrics, QShowEvent
from PySide2.QtWidgets import (
    QComboBox,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLayoutItem,
    QPushButton,
    QScrollArea,
    QStackedWidget,
    QTableView,
    QVBoxLayout,
    QWidget,
)

from finaldb.core.stats import format_size
from finaldb.gui.controllers.stats_controller import StatsController
from finaldb.gui.controllers.workspace_controller import WorkspaceController
from finaldb.gui.theme import SPACING_MD, SPACING_SM, ThemeManager
from finaldb.gui.widgets.common import caption_label, card, page_title, workspace_hint
from finaldb.gui.widgets.icons import build_icon

__all__ = ["StatsPage"]

# 条形行各列宽度（逻辑像素）：名称标签 / 行数标签
_NAME_WIDTH = 120
_ROWS_WIDTH = 56
# 指标卡数量（数据表/总行数/总列数/体积）
_METRIC_TITLES = ("数据表", "总行数", "总列数", "占用体积")
# 名称省略占位
_ELLIPSIS = "..."


def _metric_card(title: str) -> tuple[QFrame, QLabel]:
    """构建指标卡（标题 + 大数字），返回 (卡片, 数值标签)。."""
    frame = card()
    layout = QVBoxLayout(frame)
    layout.setContentsMargins(SPACING_SM + 4, SPACING_SM, SPACING_SM + 4, SPACING_SM)
    layout.setSpacing(2)
    layout.addWidget(caption_label(title))
    value = QLabel("—")
    value.setObjectName("metricValue")
    value.setAlignment(Qt.AlignCenter)
    layout.addWidget(value)
    return frame, value


class StatsPage(QWidget):
    """统计页：概览指标卡 + 左侧分布图 + 右侧质量画像与列统计表。."""

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
        self._bars: list[QWidget] = []  # 主色条（行数/类型分布）
        self._null_bars: list[QWidget] = []  # 警示色条（空值率）
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

        # ---------- 指标卡行 ----------
        metrics = QHBoxLayout()
        metrics.setSpacing(SPACING_SM)
        self._metric_values: list[QLabel] = []
        for title in _METRIC_TITLES:
            frame, value = _metric_card(title)
            metrics.addWidget(frame, stretch=1)
            self._metric_values.append(value)
        root.addLayout(metrics)

        # ---------- 主体两栏 ----------
        body = QHBoxLayout()
        body.setSpacing(SPACING_MD)

        # 左：表行数分布条形图
        left = card()
        left.setFixedWidth(300)
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

        # 右：质量画像（类型分布 | 空值 TOP）+ 列统计表
        right = QVBoxLayout()
        right.setSpacing(SPACING_MD)

        profile = QHBoxLayout()
        profile.setSpacing(SPACING_MD)

        types_card = card()
        types_layout = QVBoxLayout(types_card)
        types_layout.setContentsMargins(SPACING_SM, SPACING_SM, SPACING_SM, SPACING_SM)
        types_layout.setSpacing(SPACING_SM)
        types_layout.addWidget(caption_label("列类型分布"))
        self._types_host = QWidget()
        self._types_layout = QVBoxLayout(self._types_host)
        self._types_layout.setContentsMargins(0, 0, 0, 0)
        self._types_layout.setSpacing(SPACING_SM)
        self._types_layout.addStretch(1)
        types_layout.addWidget(self._types_host, stretch=1)
        profile.addWidget(types_card, stretch=1)

        nulls_card = card()
        nulls_layout = QVBoxLayout(nulls_card)
        nulls_layout.setContentsMargins(SPACING_SM, SPACING_SM, SPACING_SM, SPACING_SM)
        nulls_layout.setSpacing(SPACING_SM)
        nulls_layout.addWidget(caption_label("空值最多的列"))
        self._nulls_host = QWidget()
        self._nulls_layout = QVBoxLayout(self._nulls_host)
        self._nulls_layout.setContentsMargins(0, 0, 0, 0)
        self._nulls_layout.setSpacing(SPACING_SM)
        self._nulls_layout.addStretch(1)
        nulls_layout.addWidget(self._nulls_host, stretch=1)
        profile.addWidget(nulls_card, stretch=1)

        right.addLayout(profile)

        detail = card()
        detail_layout = QVBoxLayout(detail)
        detail_layout.setContentsMargins(SPACING_SM, SPACING_SM, SPACING_SM, SPACING_SM)
        detail_layout.setSpacing(SPACING_SM)

        table_row = QHBoxLayout()
        table_row.setSpacing(SPACING_SM)
        table_row.addWidget(caption_label("数据表"))
        self._table_combo = QComboBox()
        self._table_combo.setObjectName("statsTableCombo")
        self._table_combo.activated.connect(self._on_table_activated)
        table_row.addWidget(self._table_combo, stretch=1)
        detail_layout.addLayout(table_row)

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
        detail_layout.addWidget(self._stat_stack, stretch=1)
        right.addWidget(detail, stretch=1)

        body.addLayout(right, stretch=1)
        root.addLayout(body, stretch=1)

        # ---------- 信号装配 ----------
        self._stats.stats_changed.connect(self._refresh)  # pyrefly: ignore [missing-attribute]
        self._stats.table_stats_changed.connect(self._refresh)  # pyrefly: ignore [missing-attribute]
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
        """统计变化：刷新指标卡、分布图与画像区。."""
        self._reload_metrics()
        self._reload_table_combo()
        self._reload_rows_chart()
        self._reload_types()
        self._reload_nulls()
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

    def _reload_metrics(self) -> None:
        """刷新指标卡数值（概览缺失时显示占位符）。."""
        overview = self._stats.overview()
        if overview is None:
            values = ("—", "—", "—", "—")
        else:
            values = (
                str(overview.table_count),
                f"{overview.total_rows:,}",
                str(overview.total_columns),
                format_size(overview.db_bytes),
            )
        for label, text in zip(self._metric_values, values):  # noqa: B905
            label.setText(text)

    def _reload_rows_chart(self) -> None:
        """重建表行数分布条形图行。."""
        self._clear_layout(self._rows_layout, self._rows_host)
        model = self._stats.stats_model()
        for row in range(model.rowCount()):
            index = model.index(row, 0)
            name = str(model.data(index, Qt.UserRole + 1) or "")
            rows = model.data(index, Qt.UserRole + 2)
            ratio = float(model.data(index, Qt.UserRole + 5) or 0.0)
            self._rows_layout.insertLayout(self._rows_layout.count() - 1, self._build_bar_row(name, ratio, rows))

    def _reload_types(self) -> None:
        """重建列类型分布行（比例条 + 列数）。."""
        self._clear_layout(self._types_layout, self._types_host)
        types = self._stats.type_distribution()
        total = sum(count for _, count in types) or 1
        if not types:
            self._types_layout.insertWidget(self._types_layout.count() - 1, caption_label("暂无数据"))
            return
        for type_name, count in types:
            row = self._build_bar_row(type_name, count / total, f"{count} 列", name_width=_NAME_WIDTH)
            self._types_layout.insertLayout(self._types_layout.count() - 1, row)

    def _reload_nulls(self) -> None:
        """重建空值 TOP 行（警示色比例条 + 空值数/总数）。."""
        self._clear_layout(self._nulls_layout, self._nulls_host)
        nulls = self._stats.top_nulls()
        if not nulls:
            self._nulls_layout.insertWidget(self._nulls_layout.count() - 1, caption_label("无空值列"))
            return
        for item in nulls:
            ratio = item.null_count / item.total if item.total else 0.0
            label = f"{item.table}.{item.column}"
            row = self._build_bar_row(
                label, ratio, f"{item.null_count}/{item.total}", name_width=_NAME_WIDTH + 40, warning=True
            )
            self._nulls_layout.insertLayout(self._nulls_layout.count() - 1, row)

    def _clear_layout(self, layout: QVBoxLayout, host: QWidget) -> None:
        """清空布局内全部控件（保留尾部弹簧），同步移除其条形登记。."""

        def _discard_item(item: QLayoutItem) -> list[QWidget]:
            """递归释放布局项内的全部 widget（含 widget 内嵌布局），返回已删除列表。."""
            removed: list[QWidget] = []
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
                removed.append(widget)
                inner = widget.layout()
                if inner is not None:
                    while inner.count():
                        removed.extend(_discard_item(inner.takeAt(0)))
                return removed
            sub = item.layout()
            if sub is not None:
                while sub.count():
                    removed.extend(_discard_item(sub.takeAt(0)))
            return removed

        deleted: list[QWidget] = []
        while layout.count() > 1:
            deleted.extend(_discard_item(layout.takeAt(0)))
        self._bars = [bar for bar in self._bars if bar not in deleted and bar.parent() is not host]
        self._null_bars = [bar for bar in self._null_bars if bar not in deleted and bar.parent() is not host]

    def _build_bar_row(
        self,
        name: str,
        ratio: float,
        trailing: object,
        name_width: int = _NAME_WIDTH,
        warning: bool = False,
    ) -> QHBoxLayout:
        """构建单行条形图：名称（省略）| 比例条 | 尾注（右对齐）。

        Args:
            name: 名称文本（超宽中部省略）
            ratio: 填充比例 0.0~1.0
            trailing: 尾注文本（行数/列数/空值数）
            name_width: 名称固定宽
            warning: True 时条形登记为警示色（空值画像）
        """
        row = QHBoxLayout()
        row.setSpacing(SPACING_SM)
        name_label = QLabel(self._elide_middle(name, name_width))
        name_label.setFixedWidth(name_width)
        name_label.setToolTip(name)
        bar_holder = QWidget()
        holder_layout = QHBoxLayout(bar_holder)
        holder_layout.setContentsMargins(0, 0, 0, 0)
        holder_layout.setSpacing(0)
        bar = QWidget()
        bar.setFixedHeight(10)
        spacer = QWidget()
        holder_layout.addWidget(bar)
        holder_layout.addWidget(spacer)
        filled = max(1, int(ratio * 1000))
        holder_layout.setStretch(0, filled)
        holder_layout.setStretch(1, max(0, 1000 - filled))
        (self._null_bars if warning else self._bars).append(bar)
        trailing_label = caption_label(str(trailing))
        trailing_label.setFixedWidth(_ROWS_WIDTH + 24)
        trailing_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        row.addWidget(name_label)
        row.addWidget(bar_holder, stretch=1)
        row.addWidget(trailing_label)
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
        """按当前主题刷新条形颜色（分布主色 / 空值警示色）。."""
        primary = self._theme.color("primary")
        warning = self._theme.color("warning")
        for bar in self._bars:
            bar.setStyleSheet(f"background-color: {primary}; border-radius: 4px;")
        for bar in self._null_bars:
            bar.setStyleSheet(f"background-color: {warning}; border-radius: 4px;")
