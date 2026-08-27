"""数据页：工作区管理 + 数据导入 + 表列表 + 编辑面板。

整合原数据源页与数据编辑页：左侧选择工作区与表，
右侧直接编辑选中表，消除重复的表选择入口。
"""

from __future__ import annotations

from PySide2.QtCore import QSize, Qt, Signal
from PySide2.QtGui import QFont, QMouseEvent, QShowEvent
from PySide2.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from finaldb.gui.controllers.editing_controller import EditingController
from finaldb.gui.controllers.workspace_controller import (
    WorkspaceController,
    format_timestamp,
)
from finaldb.gui.theme import SPACING_MD, SPACING_SM, ThemeManager
from finaldb.gui.widgets.common import busy_bar, card, page_title, workspace_hint
from finaldb.gui.widgets.pages.edit_panel import EditPanel
from finaldb.gui.widgets.toast import Toast

__all__ = ["DataPage"]

# 导入文件选择器的名称过滤器
_IMPORT_FILTER = "数据文件 (*.csv *.tsv *.xlsx *.xlsm *.json *.ndjson);;所有文件 (*)"


class _WorkspaceCard(QWidget):
    """工作区卡片行：名称 + 概要 + 删除按钮（✕）。."""

    selected = Signal(str)
    delete_requested = Signal(str)

    def __init__(self, name: str, summary: str, parent: QWidget | None = None) -> None:
        """初始化卡片行。

        :param name: 工作区名
        :param summary: 概要文本（表数/行数/更新时间）
        """
        super().__init__(parent)
        self._name = name
        root = QVBoxLayout(self)
        root.setContentsMargins(10, 8, 6, 8)
        root.setSpacing(2)

        top = QHBoxLayout()
        top.setSpacing(6)
        name_label = QLabel(name)
        font = QFont()
        font.setBold(True)
        name_label.setFont(font)
        delete_btn = QPushButton("✕")
        delete_btn.setProperty("linkButton", True)
        delete_btn.setCursor(Qt.PointingHandCursor)
        delete_btn.setToolTip("删除工作区")
        delete_btn.clicked.connect(lambda: self.delete_requested.emit(self._name))  # pyrefly: ignore [missing-attribute]
        top.addWidget(name_label, stretch=1)
        top.addWidget(delete_btn)

        summary_label = QLabel(summary)
        summary_label.setProperty("caption", True)
        root.addLayout(top)
        root.addWidget(summary_label)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        """点击卡片任意区域即选中工作区。."""
        if event.button() == Qt.LeftButton:
            self.selected.emit(self._name)  # pyrefly: ignore [missing-attribute]
        super().mousePressEvent(event)


class DataPage(QWidget):
    """数据页：三栏布局（工作区列表 | 表列表 | 编辑面板）。."""

    def __init__(
        self,
        theme: ThemeManager,
        workspace_ctrl: WorkspaceController,
        editing_ctrl: EditingController,
        parent: QWidget | None = None,
    ) -> None:
        """初始化页面并装配控制器信号。

        Args:
            theme: 主题管理器
            workspace_ctrl: 工作区控制器
            editing_ctrl: 编辑控制器
            parent: 父部件
        """
        super().__init__(parent)
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

        # ---------- 主体三栏 ----------
        body = QHBoxLayout()
        body.setSpacing(SPACING_MD)

        # 工作区卡片列表
        ws_card = card()
        ws_card.setFixedWidth(240)
        ws_layout = QVBoxLayout(ws_card)
        ws_layout.setContentsMargins(SPACING_SM, SPACING_SM, SPACING_SM, SPACING_SM)
        self._ws_list = QListWidget()
        self._ws_list.setObjectName("wsList")
        self._ws_list.setCursor(Qt.PointingHandCursor)
        ws_layout.addWidget(self._ws_list)
        self._ws_empty = QLabel("暂无工作区\n点击右上角「新建工作区」开始")
        self._ws_empty.setProperty("caption", True)
        self._ws_empty.setAlignment(Qt.AlignCenter)
        self._ws_empty.setWordWrap(True)
        ws_layout.addWidget(self._ws_empty)
        body.addWidget(ws_card)

        # 当前工作区表列表
        table_card = card()
        table_card.setFixedWidth(180)
        table_layout = QVBoxLayout(table_card)
        table_layout.setContentsMargins(SPACING_SM, SPACING_SM, SPACING_SM, SPACING_SM)
        self._table_list = QListWidget()
        self._table_list.setObjectName("tableList")
        self._table_list.setCursor(Qt.PointingHandCursor)
        self._table_list.itemClicked.connect(self._on_table_clicked)
        table_layout.addWidget(self._table_list)
        self._table_empty = QLabel("先选择工作区")
        self._table_empty.setProperty("caption", True)
        self._table_empty.setAlignment(Qt.AlignCenter)
        self._table_empty.setWordWrap(True)
        table_layout.addWidget(self._table_empty)
        body.addWidget(table_card)

        # 编辑面板（表由左侧列表选择，点击即在原地编辑）
        self._editor = EditPanel(theme, editing_ctrl)
        body.addWidget(self._editor, stretch=1)

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

        self._refresh_workspaces()
        self._on_workspace_changed()

    # ----------------------------- 工作区 -----------------------------

    def showEvent(self, event: QShowEvent) -> None:
        """页面可见时重载表列表与编辑会话。."""
        super().showEvent(event)
        self._on_workspace_changed()

    def _refresh_workspaces(self) -> None:
        """按工作区模型重建卡片列表。."""
        model = self._ws.workspace_model()
        self._ws_list.clear()
        for row in range(model.rowCount()):
            meta = model.meta_at(row)
            if meta is None:
                continue
            item = QListWidgetItem()
            item.setSizeHint(QSize(228, 56))
            self._ws_list.addItem(item)
            summary = f"{meta.table_count} 张表 · {meta.total_rows} 行 · {format_timestamp(meta.updated_at)}"
            row_widget = _WorkspaceCard(meta.name, summary, self._ws_list)
            row_widget.selected.connect(self._on_select_workspace)  # pyrefly: ignore [missing-attribute]
            row_widget.delete_requested.connect(self._on_delete_workspace)  # pyrefly: ignore [missing-attribute]
            self._ws_list.setItemWidget(item, row_widget)
        self._ws_empty.setVisible(model.rowCount() == 0)

    def _on_select_workspace(self, name: str) -> None:
        """点击工作区卡片：选中并重载表列表。."""
        self._ws.select_workspace(name)

    def _on_delete_workspace(self, name: str) -> None:
        """点击 ✕：确认后删除工作区。."""
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
        """当前工作区切换：刷新表列表、编辑面板与按钮状态。."""
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
        """点击表项：在右侧编辑面板中打开该表。."""
        name = str(item.data(Qt.UserRole) or "")
        if name:
            self._editor.open_table(name)

    # ----------------------------- 状态 -----------------------------

    def _update_actions(self) -> None:
        """刷新忙指示与导入按钮可用态。."""
        busy = self._ws.is_busy()
        self._busy.setVisible(busy)
        self._import_btn.setEnabled(self._ws.current_workspace() != "" and not busy)
