"""数据清洗面板：表/列选择 + 清洗规则配置 + 预览与统计 + 应用到新表。

作为数据页的嵌入面板：无页标题与工作区提示（由数据页统一提供），
表数据源跟随数据页当前工作区。
"""

from __future__ import annotations

from PySide2.QtCore import QSize, Qt, Signal
from PySide2.QtGui import QShowEvent
from PySide2.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QTableView,
    QVBoxLayout,
    QWidget,
)

from finaldb.gui.controllers.clean_controller import CleanController
from finaldb.gui.controllers.workspace_controller import WorkspaceController
from finaldb.gui.theme import SPACING_MD, SPACING_SM, ThemeManager
from finaldb.gui.widgets.common import busy_bar, caption_label, card
from finaldb.gui.widgets.icons import build_icon
from finaldb.gui.widgets.toast import Toast

__all__ = ["CleanPane"]

# 规则类型下拉：标签与控制器取值一一对应（case 复用两个标签区分大小写）
_KIND_LABELS = ["去首尾空白", "转大写", "转小写", "文本替换", "文本转数值", "缺失值填充", "删除缺失行"]
_KIND_VALUES = ["trim", "case", "case", "replace", "to_number", "fill_missing", "drop_missing"]

# 需要参数值/替换文本的规则类型下拉索引
_KIND_REPLACE = 3
_KIND_FILL = 5


class _RuleRow(QWidget):
    """规则行：描述文本 + 行内「移除」按钮。."""

    remove_requested = Signal(int)

    def __init__(self, describe: str, row: int, parent: QWidget | None = None) -> None:
        """初始化规则行。

        :param describe: 规则描述文本
        :param row: 所在行号（移除时回传）
        """
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 0, 6, 0)
        layout.setSpacing(6)
        label = QLabel(describe)
        remove_btn = QPushButton("移除")
        remove_btn.setProperty("linkButton", True)
        remove_btn.setCursor(Qt.PointingHandCursor)
        remove_btn.clicked.connect(lambda: self.remove_requested.emit(row))  # pyrefly: ignore [missing-attribute]
        layout.addWidget(label, stretch=1)
        layout.addWidget(remove_btn)


class CleanPane(QWidget):
    """数据清洗面板：两栏布局（规则配置 | 预览与统计）。."""

    def __init__(
        self,
        theme: ThemeManager,
        workspace_ctrl: WorkspaceController,
        clean_ctrl: CleanController,
        parent: QWidget | None = None,
    ) -> None:
        """初始化面板并装配控制器信号。

        Args:
            theme: 主题管理器
            workspace_ctrl: 工作区控制器
            clean_ctrl: 清洗控制器
            parent: 父部件
        """
        super().__init__(parent)
        self._theme = theme
        self._ws = workspace_ctrl
        self._clean = clean_ctrl
        self._toast = Toast(self, theme)
        self._current_table = ""
        self._current_column = ""

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(SPACING_SM)

        # ---------- 顶部工具栏 ----------
        bar = QHBoxLayout()
        bar.setSpacing(SPACING_SM)
        self._busy = busy_bar()
        bar.addWidget(self._busy)
        bar.addStretch(1)
        self._preview_btn = QPushButton("预览效果")
        self._preview_btn.setObjectName("previewBtn")
        self._preview_btn.clicked.connect(self._on_preview)
        self._apply_btn = QPushButton("应用到新表")
        self._apply_btn.clicked.connect(self._on_apply)
        bar.addWidget(self._preview_btn)
        bar.addWidget(self._apply_btn)
        root.addLayout(bar)

        # ---------- 主体两栏 ----------
        body = QHBoxLayout()
        body.setSpacing(SPACING_MD)

        # 左：规则配置面板
        left = card()
        left.setFixedWidth(340)
        form = QVBoxLayout(left)
        form.setContentsMargins(12, 12, 12, 12)
        form.setSpacing(SPACING_SM)

        form.addWidget(caption_label("数据表"))
        self._table_combo = QComboBox()
        self._table_combo.setObjectName("tableCombo")
        self._table_combo.activated.connect(self._on_table_activated)
        form.addWidget(self._table_combo)

        form.addWidget(caption_label("清洗规则"))
        self._kind_combo = QComboBox()
        self._kind_combo.addItems(_KIND_LABELS)
        self._kind_combo.currentIndexChanged.connect(self._on_kind_changed)
        form.addWidget(self._kind_combo)

        form.addWidget(caption_label("目标列"))
        self._column_combo = QComboBox()
        self._column_combo.setObjectName("columnCombo")
        self._column_combo.activated.connect(self._on_column_activated)
        form.addWidget(self._column_combo)

        # 参数区（按规则类型显隐）
        self._value_row = QWidget()
        value_layout = QHBoxLayout(self._value_row)
        value_layout.setContentsMargins(0, 0, 0, 0)
        value_layout.setSpacing(SPACING_SM)
        self._value_label = caption_label("查找")
        self._value_field = QLineEdit()
        self._value_field.setPlaceholderText("必填")
        value_layout.addWidget(self._value_label)
        value_layout.addWidget(self._value_field, stretch=1)
        form.addWidget(self._value_row)

        self._replacement_row = QWidget()
        replacement_layout = QHBoxLayout(self._replacement_row)
        replacement_layout.setContentsMargins(0, 0, 0, 0)
        replacement_layout.setSpacing(SPACING_SM)
        replacement_layout.addWidget(caption_label("替换为"))
        self._replacement_field = QLineEdit()
        self._replacement_field.setPlaceholderText("替换文本（可为空）")
        replacement_layout.addWidget(self._replacement_field, stretch=1)
        form.addWidget(self._replacement_row)

        add_btn = QPushButton("添加规则")
        add_btn.clicked.connect(self._on_add_rule)
        form.addWidget(add_btn)

        form.addWidget(caption_label("已配置规则（按顺序应用）"))
        self._rule_list = QListWidget()
        self._rule_list.setObjectName("ruleList")
        form.addWidget(self._rule_list, stretch=1)
        clear_btn = QPushButton("清空规则")
        clear_btn.clicked.connect(self._clean.clear_rules)
        form.addWidget(clear_btn)
        body.addWidget(left)

        # 右：预览与统计
        right = card()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(12, 12, 12, 12)
        right_layout.setSpacing(SPACING_SM)

        head = QHBoxLayout()
        head.setSpacing(SPACING_SM)
        self._preview_title = QLabel("清洗预览")
        self._preview_title.setProperty("heading", True)
        head.addWidget(self._preview_title, stretch=1)
        self._target_caption = caption_label("新表名")
        self._target_caption.setVisible(False)
        self._target_field = QLineEdit()
        self._target_field.setFixedWidth(160)
        self._target_field.setVisible(False)
        head.addWidget(self._target_caption)
        head.addWidget(self._target_field)
        right_layout.addLayout(head)

        self._report_label = QLabel("")
        self._report_label.setProperty("caption", True)
        self._report_label.setWordWrap(True)
        self._report_label.setVisible(False)
        right_layout.addWidget(self._report_label)

        self._preview_view = QTableView()
        self._preview_view.setObjectName("cleanPreviewView")
        self._preview_view.setModel(self._clean.preview_model())
        self._preview_view.setEditTriggers(QTableView.NoEditTriggers)
        self._preview_view.setAlternatingRowColors(True)
        self._preview_view.verticalHeader().setVisible(False)
        # 列宽随内容自适应，末列拉伸占满（表格数据对齐）
        preview_header = self._preview_view.horizontalHeader()
        preview_header.setSectionResizeMode(QHeaderView.ResizeToContents)
        preview_header.setMinimumSectionSize(72)
        preview_header.setStretchLastSection(True)
        right_layout.addWidget(self._preview_view, stretch=1)
        self._preview_empty = QLabel("选择数据表后配置规则")
        self._preview_empty.setProperty("secondary", True)
        self._preview_empty.setAlignment(Qt.AlignCenter)
        self._preview_empty.setWordWrap(True)
        right_layout.addWidget(self._preview_empty)
        body.addWidget(right, stretch=1)

        root.addLayout(body, stretch=1)

        # ---------- 信号装配 ----------
        rules_model = self._clean.rules_model()
        rules_model.rowsInserted.connect(self._refresh_rules)
        rules_model.rowsRemoved.connect(self._refresh_rules)
        rules_model.modelReset.connect(self._refresh_rules)
        # 导入完成后控制器重载表模型，监听 modelReset 刷新表下拉
        self._clean.tables_model().modelReset.connect(self._on_tables_reset)
        self._clean.report_changed.connect(self._refresh_report)  # pyrefly: ignore [missing-attribute]
        self._clean.preview_model().modelReset.connect(self._update_preview_state)
        self._clean.busy_changed.connect(self._update_actions)  # pyrefly: ignore [missing-attribute]
        self._clean.applied.connect(self._toast.show_message)  # pyrefly: ignore [missing-attribute]
        self._clean.failed.connect(self._toast.show_error)  # pyrefly: ignore [missing-attribute]
        self._clean.error_raised.connect(self._toast.show_error)  # pyrefly: ignore [missing-attribute]
        self._ws.current_changed.connect(self._on_workspace_changed)  # pyrefly: ignore [missing-attribute]

        self._on_kind_changed(self._kind_combo.currentIndex())
        self._on_workspace_changed()

        # ---------- 图标装配（随主题重建；应用/添加规则无对应资产，保持纯文字） ----------
        self._icon_buttons: list[tuple[QPushButton, str]] = [
            (self._preview_btn, "preview"),
            (clear_btn, "cancel"),
        ]
        self._apply_icons()
        self._theme.theme_changed.connect(self._apply_icons)  # pyrefly: ignore [missing-attribute]

    def _apply_icons(self) -> None:
        """按当前主题为工具按钮重建图标（预览主色，清空规则正文色）。."""
        primary = self._theme.color("primary")
        text = self._theme.color("text_primary")
        for btn, name in self._icon_buttons:
            btn.setIcon(build_icon(name, primary if btn is self._preview_btn else text))

    # ----------------------------- 工作区与表 -----------------------------

    def _on_workspace_changed(self) -> None:
        """工作区切换：重置选择并重载表列表。."""
        self._current_table = ""
        self._current_column = ""
        self._clean.load_tables(self._ws.current_workspace_path())
        self._reload_combo(self._table_combo, self._tables_of_current())
        self._reload_combo(self._column_combo, [])
        self._update_preview_state()
        self._update_actions()

    def showEvent(self, event: QShowEvent) -> None:
        """面板可见时重载表列表。."""
        super().showEvent(event)
        if self._ws.current_workspace_path():
            self._clean.load_tables(self._ws.current_workspace_path())
            self._on_tables_reset()

    def _on_tables_reset(self) -> None:
        """表列表模型重置（导入完成）：刷新表下拉并校准当前选择。."""
        self._reload_combo(self._table_combo, self._tables_of_current())
        if self._current_table not in self._tables_of_current():
            self._current_table = ""
            self._current_column = ""
            self._reload_combo(self._column_combo, [])
        self._update_preview_state()
        self._update_actions()

    def _tables_of_current(self) -> list[str]:
        """当前表列表模型的全部表名。."""
        model = self._clean.tables_model()
        return [model.table_at(row) or "" for row in range(model.rowCount())]

    def _on_table_activated(self, index: int) -> None:
        """选择数据表：记录表名并加载列名。."""
        self._current_table = self._table_combo.itemText(index)
        self._current_column = ""
        self._clean.load_columns(self._ws.current_workspace_path(), self._current_table)
        model = self._clean.columns_model()
        self._reload_combo(self._column_combo, [model.item_at(row) or "" for row in range(model.rowCount())])
        self._target_field.setPlaceholderText(f"默认 {self._current_table}_clean")
        self._update_preview_state()
        self._update_actions()

    def _on_column_activated(self, index: int) -> None:
        """选择目标列。."""
        self._current_column = self._column_combo.itemText(index)

    @staticmethod
    def _reload_combo(combo: QComboBox, items: list[str]) -> None:
        """阻塞信号地整体替换下拉项（避免程序化刷新触发 activated）。."""
        combo.blockSignals(True)
        combo.clear()
        combo.addItems(items)
        combo.blockSignals(False)

    # ----------------------------- 规则配置 -----------------------------

    def _on_kind_changed(self, index: int) -> None:
        """规则类型切换：按需显隐参数区并更新标签。."""
        self._value_row.setVisible(index in (_KIND_REPLACE, _KIND_FILL))
        self._value_label.setText("填充值" if index == _KIND_FILL else "查找")
        self._replacement_row.setVisible(index == _KIND_REPLACE)

    def _on_add_rule(self) -> None:
        """添加规则：按下拉索引映射类型与大小写模式。."""
        index = self._kind_combo.currentIndex()
        kind = _KIND_VALUES[index] if 0 <= index < len(_KIND_VALUES) else ""
        case_mode = ""
        if kind == "case":
            case_mode = "upper" if index == 1 else "lower"
        self._clean.add_rule(
            kind,
            self._current_column,
            self._value_field.text(),
            self._replacement_field.text(),
            case_mode,
        )

    def _refresh_rules(self, *_args: object) -> None:
        """规则模型变化：重建规则列表（含行内移除按钮）并刷新按钮可用态。."""
        self._rule_list.clear()
        model = self._clean.rules_model()
        for row in range(model.rowCount()):
            index = model.index(row, 0)
            describe = str(model.data(index, Qt.UserRole + 6) or "")
            item = QListWidgetItem()
            item.setSizeHint(QSize(300, 34))
            self._rule_list.addItem(item)
            rule_row = _RuleRow(describe, row, self._rule_list)
            rule_row.remove_requested.connect(self._on_remove_rule)  # pyrefly: ignore [missing-attribute]
            self._rule_list.setItemWidget(item, rule_row)
        self._update_actions()

    def _on_remove_rule(self, row: int) -> None:
        """移除指定行的规则。."""
        self._clean.remove_rule(row)

    # ----------------------------- 预览与应用 -----------------------------

    def _on_preview(self) -> None:
        """对当前表前 200 行应用规则预览。."""
        self._clean.preview(self._ws.current_workspace_path(), self._current_table)

    def _on_apply(self) -> None:
        """后台清洗并写入新表。."""
        self._clean.apply(self._ws.current_workspace_path(), self._current_table, self._target_field.text())

    def _refresh_report(self) -> None:
        """刷新统计报告文本。."""
        report = self._clean.report_text()
        self._report_label.setText(report)
        self._report_label.setVisible(report != "")

    def _update_preview_state(self) -> None:
        """按选择状态切换标题与占位提示。."""
        self._preview_title.setText(f"清洗预览: {self._current_table}" if self._current_table else "清洗预览")
        self._target_caption.setVisible(self._current_table != "")
        self._target_field.setVisible(self._current_table != "")
        has_preview = self._clean.preview_model().rowCount() > 0
        self._preview_view.setVisible(has_preview)
        self._preview_empty.setVisible(not has_preview)
        if not has_preview:
            self._preview_empty.setText(
                "点击「预览效果」查看清洗后的前 200 行" if self._current_table else "选择数据表后配置规则"
            )

    # ----------------------------- 状态 -----------------------------

    def _update_actions(self) -> None:
        """刷新忙指示与预览/应用按钮可用态。."""
        busy = self._clean.is_busy()
        self._busy.setVisible(busy)
        ready = self._current_table != "" and self._clean.rules_model().rowCount() > 0
        self._preview_btn.setEnabled(ready and not busy)
        self._apply_btn.setEnabled(ready and not busy)
