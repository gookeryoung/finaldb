"""版本历史页：快照列表 + 提交 + 对比 + 回滚。."""

from __future__ import annotations

from PySide2.QtCore import Qt
from PySide2.QtGui import QColor, QFont, QShowEvent
from PySide2.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from finaldb.gui.controllers.history_controller import HistoryController
from finaldb.gui.controllers.workspace_controller import WorkspaceController
from finaldb.gui.theme import SPACING_MD, SPACING_SM, ThemeManager
from finaldb.gui.widgets.common import busy_bar, caption_label, card, page_title, workspace_hint
from finaldb.gui.widgets.toast import Toast

__all__ = ["HistoryPage"]

# 回滚目标行的前缀标记
_RESTORE_MARK = "◆ "


class HistoryPage(QWidget):
    """版本历史页：两栏布局（快照列表 | 提交与对比）。."""

    def __init__(
        self,
        theme: ThemeManager,
        workspace_ctrl: WorkspaceController,
        history_ctrl: HistoryController,
        parent: QWidget | None = None,
    ) -> None:
        """初始化页面并装配控制器信号。

        Args:
            theme: 主题管理器
            workspace_ctrl: 工作区控制器
            history_ctrl: 历史控制器
            parent: 父部件
        """
        super().__init__(parent)
        self._theme = theme
        self._ws = workspace_ctrl
        self._history = history_ctrl
        self._toast = Toast(self, theme)

        # 选中的两个快照引用（对比用，按点击顺序）与回滚目标
        self._ref_a = ""
        self._ref_b = ""
        self._restore_ref = ""

        root = QVBoxLayout(self)
        root.setContentsMargins(SPACING_MD, SPACING_MD, SPACING_MD, SPACING_MD)
        root.setSpacing(SPACING_MD)

        # ---------- 顶部工具栏 ----------
        bar = QHBoxLayout()
        bar.setSpacing(SPACING_SM)
        bar.addWidget(page_title("版本历史"))
        bar.addWidget(workspace_hint(theme, workspace_ctrl, "未选择工作区（请先在数据源页选择）"), stretch=1)
        self._busy = busy_bar()
        bar.addWidget(self._busy)
        self._diff_btn = QPushButton("对比选中")
        self._diff_btn.setObjectName("diffBtn")
        self._diff_btn.clicked.connect(self._on_diff)
        self._restore_btn = QPushButton("回滚到此")
        self._restore_btn.setObjectName("restoreBtn")
        self._restore_btn.clicked.connect(self._on_restore)
        bar.addWidget(self._diff_btn)
        bar.addWidget(self._restore_btn)
        root.addLayout(bar)

        # ---------- 主体两栏 ----------
        body = QHBoxLayout()
        body.setSpacing(SPACING_MD)

        # 左：快照列表（点击选两个对比，双击设为回滚目标）
        left = card()
        left.setFixedWidth(420)
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(12, 12, 12, 12)
        left_layout.setSpacing(SPACING_SM)
        hint = caption_label("快照（点击选两个对比，双击设为回滚目标）")
        hint.setWordWrap(True)
        left_layout.addWidget(hint)
        self._snap_list = QListWidget()
        self._snap_list.setObjectName("snapList")
        self._snap_list.setSelectionMode(QListWidget.NoSelection)
        self._snap_list.itemClicked.connect(self._on_item_clicked)
        self._snap_list.itemDoubleClicked.connect(self._on_item_double_clicked)
        left_layout.addWidget(self._snap_list, stretch=1)
        self._snap_empty = caption_label("暂无快照\n导入数据后自动创建，或在右侧手动提交")
        self._snap_empty.setAlignment(Qt.AlignCenter)
        self._snap_empty.setWordWrap(True)
        left_layout.addWidget(self._snap_empty)
        body.addWidget(left)

        # 右：手动提交 + diff 结果
        right = card()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(12, 12, 12, 12)
        right_layout.setSpacing(SPACING_SM)

        commit_row = QHBoxLayout()
        commit_row.setSpacing(SPACING_SM)
        commit_row.addWidget(caption_label("提交说明"))
        self._message_field = QLineEdit()
        self._message_field.setPlaceholderText("为当前数据打一个快照")
        self._message_field.returnPressed.connect(self._on_commit)
        commit_row.addWidget(self._message_field, stretch=1)
        self._commit_btn = QPushButton("提交快照")
        self._commit_btn.clicked.connect(self._on_commit)
        commit_row.addWidget(self._commit_btn)
        right_layout.addLayout(commit_row)

        self._diff_title = QLabel("对比结果")
        self._diff_title.setProperty("heading", True)
        right_layout.addWidget(self._diff_title)

        self._diff_view = QTextEdit()
        self._diff_view.setObjectName("diffView")
        self._diff_view.setReadOnly(True)
        diff_font = QFont("Consolas")
        self._diff_view.setFont(diff_font)
        self._diff_view.setLineWrapMode(QTextEdit.NoWrap)
        right_layout.addWidget(self._diff_view, stretch=1)
        self._diff_empty = QLabel("在左侧选择两个快照后点击「对比选中」\n查看表级差异（表集合、列与行数）")
        self._diff_empty.setProperty("secondary", True)
        self._diff_empty.setAlignment(Qt.AlignCenter)
        self._diff_empty.setWordWrap(True)
        right_layout.addWidget(self._diff_empty)
        body.addWidget(right, stretch=1)

        root.addLayout(body, stretch=1)

        # ---------- 信号装配 ----------
        self._history.busy_changed.connect(self._update_actions)  # pyrefly: ignore [missing-attribute]
        self._history.diff_changed.connect(self._refresh_diff)  # pyrefly: ignore [missing-attribute]
        self._history.applied.connect(self._on_applied)  # pyrefly: ignore [missing-attribute]
        self._history.failed.connect(self._toast.show_error)  # pyrefly: ignore [missing-attribute]
        self._history.error_raised.connect(self._toast.show_error)  # pyrefly: ignore [missing-attribute]
        self._ws.current_changed.connect(self._on_workspace_changed)  # pyrefly: ignore [missing-attribute]

        self._on_workspace_changed()

    # ----------------------------- 状态与刷新 -----------------------------

    def showEvent(self, event: QShowEvent) -> None:
        """页面可见时重载快照列表（对齐 QML onVisibleChanged）。."""
        super().showEvent(event)
        if self._ws.current_workspace_path():
            self._reload_history()

    def _on_workspace_changed(self) -> None:
        """工作区切换：清空选择并重载快照列表。."""
        self._ref_a = ""
        self._ref_b = ""
        self._restore_ref = ""
        self._reload_history()
        self._update_actions()

    def _reload_history(self) -> None:
        """加载快照列表并重建条目样式。."""
        self._history.load_history(self._ws.current_workspace_path())
        self._refresh_snapshots()

    def _refresh_snapshots(self) -> None:
        """按快照模型重建列表（双行文本 + 选中/回滚高亮）。."""
        model = self._history.snapshots_model()
        self._snap_list.clear()
        palette = self._theme.palette()
        for row in range(model.rowCount()):
            index = model.index(row, 0)
            short_id = str(model.data(index, Qt.UserRole + 1) or "")
            message = str(model.data(index, Qt.UserRole + 2) or "")
            time_text = str(model.data(index, Qt.UserRole + 3) or "")
            mark = _RESTORE_MARK if short_id == self._restore_ref else ""
            item = QListWidgetItem(f"{mark}{message}\n{short_id}  {time_text}")
            if short_id in (self._ref_a, self._ref_b):
                item.setBackground(QColor(palette["selection_strong"]))
            else:
                item.setBackground(QColor(palette["row_alt"]))
            self._snap_list.addItem(item)
        self._snap_empty.setVisible(model.rowCount() == 0)

    # ----------------------------- 选择逻辑 -----------------------------

    def _on_item_clicked(self, item: QListWidgetItem) -> None:
        """点击条目：按 A/B 顺序选中。."""
        row = self._snap_list.row(item)
        snap = self._history.snapshots_model().snapshot_at(row)
        if snap is not None:
            self._pick(snap.short_id)

    def _on_item_double_clicked(self, item: QListWidgetItem) -> None:
        """双击条目：设为回滚目标并选中。."""
        row = self._snap_list.row(item)
        snap = self._history.snapshots_model().snapshot_at(row)
        if snap is not None:
            self._restore_ref = snap.short_id
            self._pick(snap.short_id)

    def _pick(self, ref: str) -> None:
        """点击选中：A 为空选 A，否则 B 为空选 B，否则滚动更新（A←B，B←新）。."""
        if ref == self._ref_a:
            self._ref_a = ""
        elif ref == self._ref_b:
            self._ref_b = ""
        elif self._ref_a == "":
            self._ref_a = ref
        elif self._ref_b == "":
            self._ref_b = ref
        else:
            self._ref_a = self._ref_b
            self._ref_b = ref
        self._refresh_snapshots()
        self._update_actions()

    # ----------------------------- 操作 -----------------------------

    def _on_commit(self) -> None:
        """提交当前数据为快照。."""
        self._history.commit(self._ws.current_workspace_path(), self._message_field.text())

    def _on_diff(self) -> None:
        """对比选中的两个快照。."""
        self._history.diff(self._ws.current_workspace_path(), self._ref_a, self._ref_b)

    def _on_restore(self) -> None:
        """回滚到指定快照。."""
        self._history.restore(self._ws.current_workspace_path(), self._restore_ref)

    def _on_applied(self, message: str) -> None:
        """版本操作成功：提示并刷新快照列表。."""
        self._toast.show_message(message)
        self._reload_history()

    # ----------------------------- 状态 -----------------------------

    def _refresh_diff(self) -> None:
        """diff 文本变化：刷新显示与标题。."""
        diff = self._history.diff_text()
        self._diff_view.setPlainText(diff)
        self._diff_view.setVisible(diff != "")
        self._diff_empty.setVisible(diff == "")
        self._diff_title.setText(f"对比 {self._ref_a} → {self._ref_b}" if self._ref_a and self._ref_b else "对比结果")

    def _update_actions(self) -> None:
        """刷新忙指示与对比/回滚按钮可用态。."""
        busy = self._history.is_busy()
        self._busy.setVisible(busy)
        self._diff_btn.setEnabled(self._ref_a != "" and self._ref_b != "" and not busy)
        self._restore_btn.setEnabled(self._restore_ref != "" and not busy)
        self._commit_btn.setEnabled(not busy)
