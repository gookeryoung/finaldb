"""合并去重页：纵向合并（union）/ 表去重（dedup）/ 两表连接（join）三模式。."""

from __future__ import annotations

from PySide2.QtCore import Qt
from PySide2.QtGui import QShowEvent
from PySide2.QtWidgets import (
    QButtonGroup,
    QComboBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from finaldb.gui.controllers.merge_controller import MergeController
from finaldb.gui.controllers.workspace_controller import WorkspaceController
from finaldb.gui.theme import SPACING_MD, SPACING_SM, ThemeManager
from finaldb.gui.widgets.common import busy_bar, caption_label, card, page_title, workspace_hint
from finaldb.gui.widgets.toast import Toast

__all__ = ["MergePage"]

# 多值分隔符：与控制器侧约定一致（\x1f 单元分隔符）
_UNIT_SEP = "\x1f"

# 模式说明文案（右侧面板，随模式切换）
_MODE_TITLES = ["纵向合并", "表去重", "两表连接"]
_MODE_DESCRIPTIONS = [
    "将多个结构相似的表按顺序纵向堆叠为一张新表。\n\n列按名称对齐：首表列序优先，新列追加，缺失补空值。\n至少选择两个表。",
    "对单表去重并写入新表（原表不动）。\n\n按所选键列组合判重，键相同保留首次出现的行；不选键列则按整行判重。",
    "按左右键列把右表字段拼到左表，写入新表。\n\n内连接只保留匹配行；左连接保留左表全部行，无匹配的右字段补空。"
    "右表同名列自动加 _2 后缀，一键多匹配会展开为多行。",
]

# 连接方式下拉/按钮标签 → 控制器取值
_HOW_LABELS = ["内连接（仅匹配行）", "左连接（保留左表全部）"]
_HOW_VALUES = ["inner", "left"]


class MergePage(QWidget):
    """合并去重页：两栏布局（模式配置 | 模式说明）。."""

    def __init__(
        self,
        theme: ThemeManager,
        workspace_ctrl: WorkspaceController,
        merge_ctrl: MergeController,
        parent: QWidget | None = None,
    ) -> None:
        """初始化页面并装配控制器信号。

        Args:
            theme: 主题管理器
            workspace_ctrl: 工作区控制器
            merge_ctrl: 合并控制器
            parent: 父部件
        """
        super().__init__(parent)
        self._theme = theme
        self._ws = workspace_ctrl
        self._merge = merge_ctrl
        self._toast = Toast(self, theme)

        # 各模式选中状态
        self._union_tables: list[str] = []
        self._dedup_table = ""
        self._dedup_keys: list[str] = []
        self._join_left = ""
        self._join_right = ""
        self._join_left_key = ""
        self._join_right_key = ""
        self._join_how = _HOW_VALUES[0]

        root = QVBoxLayout(self)
        root.setContentsMargins(SPACING_MD, SPACING_MD, SPACING_MD, SPACING_MD)
        root.setSpacing(SPACING_MD)

        # ---------- 顶部工具栏：模式切换 + 工作区 + 执行 ----------
        bar = QHBoxLayout()
        bar.setSpacing(SPACING_SM)
        bar.addWidget(page_title("合并去重"))
        self._mode_group = QButtonGroup(self)
        self._mode_group.setExclusive(True)
        for index, title in enumerate(_MODE_TITLES):
            mode_btn = QPushButton(title)
            mode_btn.setProperty("modeButton", True)
            mode_btn.setCheckable(True)
            mode_btn.setChecked(index == 0)
            mode_btn.setCursor(Qt.PointingHandCursor)
            self._mode_group.addButton(mode_btn, index)
            mode_btn.clicked.connect(lambda _=False, idx=index: self._on_mode_changed(idx))
            bar.addWidget(mode_btn)
        bar.addWidget(workspace_hint(theme, workspace_ctrl, "未选择工作区（请先在数据页选择）"), stretch=1)
        self._busy = busy_bar()
        bar.addWidget(self._busy)
        self._apply_btn = QPushButton("执行")
        self._apply_btn.setObjectName("mergeApplyBtn")
        self._apply_btn.clicked.connect(self._on_apply)
        bar.addWidget(self._apply_btn)
        root.addLayout(bar)

        # ---------- 主体两栏 ----------
        body = QHBoxLayout()
        body.setSpacing(SPACING_MD)

        # 左：当前模式的配置面板
        left = card()
        left.setFixedWidth(400)
        config = QVBoxLayout(left)
        config.setContentsMargins(12, 12, 12, 12)
        config.setSpacing(SPACING_SM)
        self._stack = QStackedWidget()
        self._stack.addWidget(self._build_union_pane())
        self._stack.addWidget(self._build_dedup_pane())
        self._stack.addWidget(self._build_join_pane())
        config.addWidget(self._stack, stretch=1)

        target_row = QHBoxLayout()
        target_row.setSpacing(SPACING_SM)
        target_row.addWidget(caption_label("新表名"))
        self._target_field = QLineEdit()
        self._target_field.setPlaceholderText("默认自动命名")
        target_row.addWidget(self._target_field, stretch=1)
        config.addLayout(target_row)
        body.addWidget(left)

        # 右：模式说明
        right = card()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(12, 12, 12, 12)
        right_layout.setSpacing(SPACING_SM)
        self._mode_title = QLabel(_MODE_TITLES[0])
        self._mode_title.setProperty("heading", True)
        self._mode_desc = QLabel(_MODE_DESCRIPTIONS[0])
        self._mode_desc.setProperty("secondary", True)
        self._mode_desc.setWordWrap(True)
        self._mode_desc.setAlignment(Qt.AlignTop | Qt.AlignLeft)
        right_layout.addWidget(self._mode_title)
        right_layout.addWidget(self._mode_desc, stretch=1)
        body.addWidget(right, stretch=1)

        root.addLayout(body, stretch=1)

        # ---------- 信号装配 ----------
        self._merge.busy_changed.connect(self._update_actions)  # pyrefly: ignore [missing-attribute]
        # 导入/合并完成后控制器重载表模型，监听 modelReset 刷新各模式面板
        self._merge.tables_model().modelReset.connect(self._refresh_table_widgets)
        self._merge.applied.connect(self._toast.show_message)  # pyrefly: ignore [missing-attribute]
        self._merge.failed.connect(self._toast.show_error)  # pyrefly: ignore [missing-attribute]
        self._merge.error_raised.connect(self._toast.show_error)  # pyrefly: ignore [missing-attribute]
        self._ws.current_changed.connect(self._on_workspace_changed)  # pyrefly: ignore [missing-attribute]

        self._update_actions()

    # ----------------------------- 面板构建 -----------------------------

    def _build_union_pane(self) -> QWidget:
        """构建模式 0：纵向合并多选表面板。."""
        pane = QWidget()
        layout = QVBoxLayout(pane)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(SPACING_SM)
        caption = caption_label("选择多个表（按顺序纵向堆叠，列按名称对齐）")
        caption.setWordWrap(True)
        layout.addWidget(caption)
        self._union_count = caption_label("已选 0 个表")
        layout.addWidget(self._union_count)
        self._union_list = QListWidget()
        self._union_list.setObjectName("unionList")
        self._union_list.setSelectionMode(QListWidget.MultiSelection)
        self._union_list.itemClicked.connect(self._on_union_item_clicked)
        layout.addWidget(self._union_list, stretch=1)
        self._union_empty = caption_label("工作区暂无数据表\n请先在数据页导入")
        self._union_empty.setAlignment(Qt.AlignCenter)
        self._union_empty.setWordWrap(True)
        layout.addWidget(self._union_empty)
        return pane

    def _build_dedup_pane(self) -> QWidget:
        """构建模式 1：表去重面板。."""
        pane = QWidget()
        layout = QVBoxLayout(pane)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(SPACING_SM)
        layout.addWidget(caption_label("数据表"))
        self._dedup_combo = QComboBox()
        self._dedup_combo.setObjectName("dedupTableCombo")
        self._dedup_combo.activated.connect(self._on_dedup_table_activated)
        layout.addWidget(self._dedup_combo)
        layout.addWidget(caption_label("去重键（不选 = 按整行去重，保留首次出现）"))
        self._dedup_list = QListWidget()
        self._dedup_list.setObjectName("dedupKeysList")
        self._dedup_list.setSelectionMode(QListWidget.MultiSelection)
        self._dedup_list.itemClicked.connect(self._on_dedup_key_clicked)
        layout.addWidget(self._dedup_list, stretch=1)
        self._dedup_empty = caption_label("选择数据表后配置键列")
        self._dedup_empty.setAlignment(Qt.AlignCenter)
        self._dedup_empty.setWordWrap(True)
        layout.addWidget(self._dedup_empty)
        return pane

    def _build_join_pane(self) -> QWidget:
        """构建模式 2：两表连接面板。."""
        pane = QWidget()
        layout = QVBoxLayout(pane)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(SPACING_SM)
        layout.addWidget(caption_label("左表 / 右表"))
        tables_row = QHBoxLayout()
        tables_row.setSpacing(SPACING_SM)
        self._left_combo = QComboBox()
        self._left_combo.setObjectName("joinLeftCombo")
        self._left_combo.activated.connect(self._on_join_table_activated)
        self._right_combo = QComboBox()
        self._right_combo.setObjectName("joinRightCombo")
        self._right_combo.activated.connect(self._on_join_table_activated)
        tables_row.addWidget(self._left_combo, stretch=1)
        tables_row.addWidget(self._right_combo, stretch=1)
        layout.addLayout(tables_row)
        layout.addWidget(caption_label("左键列 / 右键列"))
        keys_row = QHBoxLayout()
        keys_row.setSpacing(SPACING_SM)
        self._left_key_combo = QComboBox()
        self._left_key_combo.activated.connect(self._on_left_key_activated)
        self._right_key_combo = QComboBox()
        self._right_key_combo.activated.connect(self._on_right_key_activated)
        keys_row.addWidget(self._left_key_combo, stretch=1)
        keys_row.addWidget(self._right_key_combo, stretch=1)
        layout.addLayout(keys_row)
        layout.addWidget(caption_label("连接方式"))
        how_row = QHBoxLayout()
        how_row.setSpacing(4)
        self._how_group = QButtonGroup(self)
        self._how_group.setExclusive(True)
        for index, label in enumerate(_HOW_LABELS):
            how_btn = QPushButton(label)
            how_btn.setProperty("modeButton", True)
            how_btn.setCheckable(True)
            how_btn.setChecked(index == 0)
            how_btn.setCursor(Qt.PointingHandCursor)
            self._how_group.addButton(how_btn, index)
            how_btn.clicked.connect(lambda _=False, idx=index: self._set_join_how(_HOW_VALUES[idx]))
            how_row.addWidget(how_btn)
        how_row.addStretch(1)
        layout.addLayout(how_row)
        layout.addStretch(1)
        return pane

    # ----------------------------- 状态与刷新 -----------------------------

    def showEvent(self, event: QShowEvent) -> None:
        """页面可见时重载表列表（对齐 QML onVisibleChanged）。."""
        super().showEvent(event)
        if self._ws.current_workspace_path():
            self._reload_tables()

    def _on_workspace_changed(self) -> None:
        """工作区切换：重置选择并重载表列表。."""
        self._union_tables = []
        self._dedup_table = ""
        self._dedup_keys = []
        self._join_left = ""
        self._join_right = ""
        self._join_left_key = ""
        self._join_right_key = ""
        self._target_field.clear()
        self._reload_tables()
        self._update_actions()

    def _reload_tables(self) -> None:
        """重载表列表并刷新各模式面板。."""
        self._merge.load_tables(self._ws.current_workspace_path())
        self._refresh_table_widgets()

    def _refresh_table_widgets(self) -> None:
        """按合并控制器表模型刷新各模式面板（不触发重载）。."""
        model = self._merge.tables_model()
        names: list[str] = []
        self._union_list.clear()
        for row in range(model.rowCount()):
            index = model.index(row, 0)
            name = model.table_at(row) or ""
            rows = model.data(index, Qt.UserRole + 2)
            names.append(name)
            item = QListWidgetItem(f"{name}（{rows} 行）")
            item.setData(Qt.UserRole, name)
            self._union_list.addItem(item)
        self._union_empty.setVisible(model.rowCount() == 0)
        self._update_union_count()
        self._reload_combo(self._dedup_combo, names)
        self._reload_combo(self._left_combo, names)
        self._reload_combo(self._right_combo, names)
        self._reload_combo(self._left_key_combo, [])
        self._reload_combo(self._right_key_combo, [])

    @staticmethod
    def _reload_combo(combo: QComboBox, items: list[str]) -> None:
        """阻塞信号地整体替换下拉项。."""
        combo.blockSignals(True)
        combo.clear()
        combo.addItems(items)
        combo.blockSignals(False)

    def _on_mode_changed(self, index: int) -> None:
        """切换模式：更新配置面板与右侧说明。."""
        self._stack.setCurrentIndex(index)
        self._mode_title.setText(_MODE_TITLES[index])
        self._mode_desc.setText(_MODE_DESCRIPTIONS[index])
        self._update_actions()

    # ----------------------------- 模式 0：纵向合并 -----------------------------

    def _on_union_item_clicked(self, item: QListWidgetItem) -> None:
        """点击表项：按选中顺序维护表清单。."""
        name = str(item.data(Qt.UserRole) or "")
        if name in self._union_tables:
            self._union_tables.remove(name)
        else:
            self._union_tables.append(name)
        self._update_union_count()
        self._update_actions()

    def _update_union_count(self) -> None:
        """刷新已选表计数。."""
        self._union_count.setText(f"已选 {len(self._union_tables)} 个表")

    # ----------------------------- 模式 1：表去重 -----------------------------

    def _on_dedup_table_activated(self, index: int) -> None:
        """选择去重表：记录表名并加载键列候选。."""
        self._dedup_table = self._dedup_combo.itemText(index)
        self._dedup_keys = []
        self._merge.load_columns(self._ws.current_workspace_path(), self._dedup_table)
        model = self._merge.dedup_columns_model()
        self._dedup_list.clear()
        for row in range(model.rowCount()):
            self._dedup_list.addItem(model.item_at(row) or "")
        has_table = self._dedup_table != ""
        has_columns = model.rowCount() > 0
        self._dedup_empty.setText(
            "" if has_table and has_columns else ("该表无列" if has_table else "选择数据表后配置键列")
        )
        self._dedup_empty.setVisible(not has_columns)
        self._update_actions()

    def _on_dedup_key_clicked(self, item: QListWidgetItem) -> None:
        """点击键列项：按选中顺序维护键清单。."""
        name = item.text()
        if name in self._dedup_keys:
            self._dedup_keys.remove(name)
        else:
            self._dedup_keys.append(name)
        self._update_actions()

    # ----------------------------- 模式 2：两表连接 -----------------------------

    def _on_join_table_activated(self, _index: int = 0) -> None:
        """左右表选择变化：记录表名并加载键列候选。."""
        if self._left_combo.count() > 0:
            self._join_left = self._left_combo.currentText()
        if self._right_combo.count() > 0:
            self._join_right = self._right_combo.currentText()
        self._join_left_key = ""
        self._join_right_key = ""
        self._merge.load_join_columns(self._ws.current_workspace_path(), self._join_left, self._join_right)
        left_model = self._merge.left_columns_model()
        right_model = self._merge.right_columns_model()
        self._reload_combo(self._left_key_combo, [left_model.item_at(r) or "" for r in range(left_model.rowCount())])
        self._reload_combo(self._right_key_combo, [right_model.item_at(r) or "" for r in range(right_model.rowCount())])
        self._update_actions()

    def _set_join_key(self, key: str, is_left: bool) -> None:
        """记录左右键列选择。."""
        if is_left:
            self._join_left_key = key
        else:
            self._join_right_key = key
        self._update_actions()

    def _on_left_key_activated(self, index: int) -> None:
        """左键列下拉激活：记录所选键列。."""
        self._set_join_key(self._left_key_combo.itemText(index), is_left=True)

    def _on_right_key_activated(self, index: int) -> None:
        """右键列下拉激活：记录所选键列。."""
        self._set_join_key(self._right_key_combo.itemText(index), is_left=False)

    def _set_join_how(self, how: str) -> None:
        """记录连接方式。."""
        self._join_how = how

    # ----------------------------- 执行 -----------------------------

    def _can_apply(self) -> bool:
        """当前模式是否具备执行条件。."""
        if not self._ws.current_workspace():
            return False
        mode = self._stack.currentIndex()
        if mode == 0:
            return len(self._union_tables) >= 2
        if mode == 1:
            return self._dedup_table != ""
        return (
            self._join_left != ""
            and self._join_right != ""
            and self._join_left_key != ""
            and self._join_right_key != ""
        )

    def _on_apply(self) -> None:
        """按当前模式发起后台合并。."""
        path = self._ws.current_workspace_path()
        mode = self._stack.currentIndex()
        if mode == 0:
            self._merge.apply_union(path, _UNIT_SEP.join(self._union_tables), self._target_field.text())
        elif mode == 1:
            self._merge.apply_dedup(
                path, self._dedup_table, _UNIT_SEP.join(self._dedup_keys), self._target_field.text()
            )
        else:
            params = [
                self._join_left,
                self._join_right,
                self._join_left_key,
                self._join_right_key,
                self._join_how,
                self._target_field.text(),
            ]
            self._merge.apply_join(path, _UNIT_SEP.join(params))

    # ----------------------------- 状态 -----------------------------

    def _update_actions(self) -> None:
        """刷新忙指示与执行按钮可用态。."""
        busy = self._merge.is_busy()
        self._busy.setVisible(busy)
        self._apply_btn.setEnabled(self._can_apply() and not busy)
