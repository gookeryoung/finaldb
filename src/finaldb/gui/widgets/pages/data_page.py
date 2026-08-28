"""数据页：工作区/表选择面板 + 数据操作三模式（编辑/清洗/合并去重）。

左侧单面板承载工作区下拉与表列表（替代原双卡片），右侧按模式按钮切换
编辑面板、清洗面板与合并去重面板——数据操作整合在同一入口下。
"""

from __future__ import annotations

from PySide2.QtCore import Qt
from PySide2.QtGui import QShowEvent
from PySide2.QtWidgets import (
    QButtonGroup,
    QComboBox,
    QFileDialog,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from finaldb.gui.controllers.clean_controller import CleanController
from finaldb.gui.controllers.editing_controller import EditingController
from finaldb.gui.controllers.merge_controller import MergeController
from finaldb.gui.controllers.workspace_controller import WorkspaceController
from finaldb.gui.theme import SPACING_MD, SPACING_SM, ThemeManager
from finaldb.gui.widgets.common import busy_bar, caption_label, card, page_title, workspace_hint
from finaldb.gui.widgets.icons import build_icon
from finaldb.gui.widgets.pages.clean_pane import CleanPane
from finaldb.gui.widgets.pages.edit_panel import EditPanel
from finaldb.gui.widgets.pages.merge_pane import MergePane
from finaldb.gui.widgets.toast import Toast

__all__ = ["DataPage"]

# 导入文件选择器的名称过滤器
_IMPORT_FILTER = "数据文件 (*.csv *.tsv *.xlsx *.xlsm *.json *.ndjson);;所有文件 (*)"

# 数据操作模式标题（与右侧面板栈顺序一致）
_MODE_TITLES = ("编辑", "数据清洗", "合并去重")
# 模式图标名（与 _MODE_TITLES 一一对应，均来自用户资产）
_MODE_ICONS = ("edit", "wash_data", "merge_data")


class DataPage(QWidget):
    """数据页：左（工作区下拉 + 表列表）| 右（模式按钮 + 操作面板栈）。."""

    def __init__(
        self,
        theme: ThemeManager,
        workspace_ctrl: WorkspaceController,
        editing_ctrl: EditingController,
        clean_ctrl: CleanController,
        merge_ctrl: MergeController,
    ) -> None:
        """初始化页面并装配控制器信号。

        Args:
            theme: 主题管理器
            workspace_ctrl: 工作区控制器
            editing_ctrl: 编辑控制器
            clean_ctrl: 清洗控制器
            merge_ctrl: 合并控制器
        """
        super().__init__()
        self._theme = theme
        self._ws = workspace_ctrl
        self._edit = editing_ctrl
        self._toast = Toast(self, theme)

        root = QVBoxLayout(self)
        root.setContentsMargins(SPACING_MD, SPACING_MD, SPACING_MD, SPACING_MD)
        root.setSpacing(SPACING_MD)

        # ---------- 顶部工具栏 ----------
        bar = QHBoxLayout()
        bar.setSpacing(SPACING_SM)
        bar.addWidget(page_title("数据"))
        bar.addWidget(workspace_hint(theme, workspace_ctrl), stretch=1)
        self._busy = busy_bar()
        bar.addWidget(self._busy)
        self._new_btn = QPushButton("新建工作区")
        self._new_btn.clicked.connect(self._on_new_workspace)
        self._import_btn = QPushButton("导入数据")
        self._import_btn.clicked.connect(self._on_import)
        bar.addWidget(self._new_btn)
        bar.addWidget(self._import_btn)
        root.addLayout(bar)

        # ---------- 主体两栏 ----------
        body = QHBoxLayout()
        body.setSpacing(SPACING_MD)

        # 左：工作区下拉 + 表列表（单面板）
        left = card()
        left.setFixedWidth(230)
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(SPACING_SM, SPACING_SM, SPACING_SM, SPACING_SM)
        left_layout.setSpacing(SPACING_SM)

        left_layout.addWidget(caption_label("工作区"))
        ws_row = QHBoxLayout()
        ws_row.setSpacing(SPACING_SM)
        self._ws_combo = QComboBox()
        self._ws_combo.setObjectName("workspaceCombo")
        self._ws_combo.activated.connect(self._on_workspace_activated)
        ws_row.addWidget(self._ws_combo, stretch=1)
        self._ws_delete_btn = QPushButton()
        self._ws_delete_btn.setProperty("linkButton", True)
        self._ws_delete_btn.setCursor(Qt.PointingHandCursor)
        self._ws_delete_btn.setToolTip("删除当前工作区")
        self._ws_delete_btn.clicked.connect(self._on_delete_workspace_clicked)
        ws_row.addWidget(self._ws_delete_btn)
        left_layout.addLayout(ws_row)

        left_layout.addWidget(caption_label("数据表"))
        self._table_list = QListWidget()
        self._table_list.setObjectName("tableList")
        self._table_list.setCursor(Qt.PointingHandCursor)
        self._table_list.itemClicked.connect(self._on_table_clicked)
        left_layout.addWidget(self._table_list, stretch=1)
        self._table_empty = QLabel("先选择工作区")
        self._table_empty.setProperty("caption", True)
        self._table_empty.setAlignment(Qt.AlignCenter)
        self._table_empty.setWordWrap(True)
        left_layout.addWidget(self._table_empty)
        body.addWidget(left)

        # 右：模式按钮 + 操作面板栈
        right = QVBoxLayout()
        right.setSpacing(SPACING_SM)

        mode_row = QHBoxLayout()
        mode_row.setSpacing(SPACING_SM)
        self._mode_group = QButtonGroup(self)
        self._mode_group.setExclusive(True)
        self._mode_buttons: list[QPushButton] = []
        for index, title in enumerate(_MODE_TITLES):
            mode_btn = QPushButton(title)
            mode_btn.setProperty("modeButton", True)
            mode_btn.setCheckable(True)
            mode_btn.setChecked(index == 0)
            mode_btn.setCursor(Qt.PointingHandCursor)
            self._mode_group.addButton(mode_btn, index)
            mode_btn.clicked.connect(lambda _=False, idx=index: self._stack.setCurrentIndex(idx))
            mode_row.addWidget(mode_btn)
            self._mode_buttons.append(mode_btn)
        mode_row.addStretch(1)
        right.addLayout(mode_row)

        self._stack = QStackedWidget()
        self._editor = EditPanel(theme, editing_ctrl)
        self._clean_pane = CleanPane(theme, workspace_ctrl, clean_ctrl)
        self._merge_pane = MergePane(theme, workspace_ctrl, merge_ctrl)
        self._stack.addWidget(self._editor)
        self._stack.addWidget(self._clean_pane)
        self._stack.addWidget(self._merge_pane)
        right.addWidget(self._stack, stretch=1)
        body.addLayout(right, stretch=1)

        root.addLayout(body, stretch=1)

        # ---------- 信号装配 ----------
        self._ws.workspaces_changed.connect(self._refresh_workspaces)  # pyrefly: ignore [missing-attribute]
        self._ws.current_changed.connect(self._on_workspace_changed)  # pyrefly: ignore [missing-attribute]
        self._ws.busy_changed.connect(self._update_actions)  # pyrefly: ignore [missing-attribute]
        # 导入完成后控制器重载表模型，监听 modelReset 刷新表列表
        self._ws.table_model().modelReset.connect(self._refresh_tables)
        self._ws.import_finished.connect(self._toast.show_message)  # pyrefly: ignore [missing-attribute]
        self._ws.import_failed.connect(self._toast.show_error)  # pyrefly: ignore [missing-attribute]
        self._ws.error_raised.connect(self._toast.show_error)  # pyrefly: ignore [missing-attribute]
        # 编辑增删行后刷新表列表行数（编辑控制器整表重载时同步）
        self._edit.tables_model().modelReset.connect(self._ws.reload_tables)

        self._refresh_workspaces()
        self._on_workspace_changed()

        # ---------- 图标装配（随主题重建） ----------
        self._icon_buttons: list[tuple[QPushButton, str, str]] = [
            (self._new_btn, "new", "primary"),
            (self._import_btn, "import_data", "primary"),
            (self._ws_delete_btn, "question", "danger"),
        ]
        # 模式按钮随主题换色（选中主色底前景 / 未选中正文色）；
        # 选中态切换同样重绘（图标色随状态）
        for index, mode_btn in enumerate(self._mode_buttons):
            self._icon_buttons.append((mode_btn, _MODE_ICONS[index], "mode"))
            mode_btn.toggled.connect(self._apply_icons)
        self._apply_icons()
        self._theme.theme_changed.connect(self._apply_icons)  # pyrefly: ignore [missing-attribute]

    def _apply_icons(self) -> None:
        """按当前主题为工具栏与模式按钮重建图标。

        颜色与按钮分级一致：primary 取主色底上的前景色、
        danger 取危险色、mode 按选中态取主色底前景或正文色；
        主题切换时整体重绘。
        """
        for btn, name, level in self._icon_buttons:
            if level == "danger":
                color = self._theme.color("danger")
            elif level == "mode":
                on_primary = btn.isChecked()
                color = self._theme.color("text_on_primary") if on_primary else self._theme.color("text_primary")
            else:
                color = self._theme.color("text_on_primary")
            btn.setIcon(build_icon(name, color))

    # ----------------------------- 工作区 -----------------------------

    def showEvent(self, event: QShowEvent) -> None:
        """页面可见时重载表列表与编辑会话。."""
        super().showEvent(event)
        self._on_workspace_changed()

    def _refresh_workspaces(self) -> None:
        """按工作区模型重建下拉项并同步当前选中。."""
        model = self._ws.workspace_model()
        names: list[str] = []
        for row in range(model.rowCount()):
            meta = model.meta_at(row)
            names.append(meta.name if meta else "")
        self._ws_combo.blockSignals(True)
        self._ws_combo.clear()
        self._ws_combo.addItems(names)
        current = self._ws.current_workspace()
        if current in names:
            self._ws_combo.setCurrentText(current)
        self._ws_combo.blockSignals(False)

    def _on_workspace_activated(self, index: int) -> None:
        """下拉选择工作区。."""
        name = self._ws_combo.itemText(index)
        if name:
            self._ws.select_workspace(name)

    def _on_delete_workspace_clicked(self) -> None:
        """删除按钮：确认后删除当前工作区。."""
        name = self._ws.current_workspace()
        if not name:
            self._toast.show_message("请先选择工作区")
            return
        self._on_delete_workspace(name)

    def _on_delete_workspace(self, name: str) -> None:
        """确认后删除工作区。."""
        answer = QMessageBox.question(
            self,
            "删除工作区",
            f"确认删除工作区「{name}」？\n所有数据将被移除且不可恢复。",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if answer == QMessageBox.Yes:
            self._ws.delete_workspace(name)

    def _on_new_workspace(self) -> None:
        """新建工作区对话框。."""
        name, ok = QInputDialog.getText(self, "新建工作区", "名称（字母/数字/下划线/连字符）")
        if ok and name.strip():
            self._ws.create_workspace(name.strip())

    def _on_import(self) -> None:
        """选择数据文件并后台导入。."""
        path, _ = QFileDialog.getOpenFileName(self, "选择数据文件", "", _IMPORT_FILTER)
        if path:
            self._ws.import_file(path)

    def _on_workspace_changed(self) -> None:
        """当前工作区切换：同步下拉、刷新表列表/编辑面板与按钮状态。."""
        current = self._ws.current_workspace()
        if self._ws_combo.currentText() != current:
            self._ws_combo.blockSignals(True)
            self._ws_combo.setCurrentText(current)
            self._ws_combo.blockSignals(False)
        self._refresh_tables()
        self._editor.refresh_tables(self._ws.current_workspace_path())
        self._update_actions()

    # ----------------------------- 表与编辑 -----------------------------

    def _refresh_tables(self) -> None:
        """按表模型重建表列表。."""
        model = self._ws.table_model()
        self._table_list.clear()
        for row in range(model.rowCount()):
            index = model.index(row, 0)
            name = model.table_at(row) or ""
            rows = model.data(index, Qt.UserRole + 2)
            item = QListWidgetItem(f"{name} ({rows})")
            item.setData(Qt.UserRole, name)
            self._table_list.addItem(item)
        has_workspace = self._ws.current_workspace() != ""
        has_tables = model.rowCount() > 0
        self._table_empty.setText("无数据表\n导入数据后显示" if has_workspace else "先选择工作区")
        self._table_empty.setVisible(not has_tables)

    def _on_table_clicked(self, item: QListWidgetItem) -> None:
        """点击表项：切到编辑模式并打开该表。."""
        name = str(item.data(Qt.UserRole) or "")
        if name:
            self._mode_group.button(0).setChecked(True)
            self._stack.setCurrentIndex(0)
            self._editor.open_table(name)

    # ----------------------------- 状态 -----------------------------

    def _update_actions(self) -> None:
        """刷新忙指示与导入按钮可用态。."""
        busy = self._ws.is_busy()
        self._busy.setVisible(busy)
        self._import_btn.setEnabled(self._ws.current_workspace() != "" and not busy)
