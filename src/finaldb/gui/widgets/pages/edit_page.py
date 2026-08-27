"""数据编辑页：表选择 + 可编辑表格 + 行列操作 + 分页 + 撤销重做。."""

from __future__ import annotations

from PySide2.QtCore import Qt
from PySide2.QtGui import QKeySequence, QShowEvent
from PySide2.QtWidgets import (
    QApplication,
    QComboBox,
    QHBoxLayout,
    QInputDialog,
    QMessageBox,
    QPushButton,
    QShortcut,
    QTableView,
    QVBoxLayout,
    QWidget,
)

from finaldb.gui.controllers.editing_controller import EditingController
from finaldb.gui.controllers.workspace_controller import WorkspaceController
from finaldb.gui.theme import SPACING_MD, SPACING_SM, ThemeManager
from finaldb.gui.widgets.common import caption_label, card, page_title, workspace_hint
from finaldb.gui.widgets.toast import Toast

__all__ = ["EditPage"]


class EditPage(QWidget):
    """数据编辑页：工具栏（表/撤销/行列操作）+ 编辑表格 + 分页条。."""

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
        bar.addWidget(page_title("数据编辑"))
        bar.addWidget(workspace_hint(theme, workspace_ctrl, "未选择工作区（请先在数据源页选择）"), stretch=1)
        root.addLayout(bar)

        # ---------- 工具行：表选择 + 撤销重做 + 行列操作 ----------
        tools = QHBoxLayout()
        tools.setSpacing(SPACING_SM)
        tools.addWidget(caption_label("数据表"))
        self._table_combo = QComboBox()
        self._table_combo.setMinimumWidth(180)
        self._table_combo.activated.connect(self._on_table_activated)
        tools.addWidget(self._table_combo)

        self._undo_btn = QPushButton("撤销")
        self._undo_btn.setToolTip("撤销上一步编辑")
        self._undo_btn.clicked.connect(self._edit.undo)
        self._redo_btn = QPushButton("重做")
        self._redo_btn.setToolTip("重做被撤销的编辑")
        self._redo_btn.clicked.connect(self._edit.redo)
        tools.addWidget(self._undo_btn)
        tools.addWidget(self._redo_btn)

        self._add_row_btn = QPushButton("加行")
        self._add_row_btn.setToolTip("在表末尾追加一行")
        self._add_row_btn.clicked.connect(self._on_add_row)
        self._del_row_btn = QPushButton("删行")
        self._del_row_btn.setToolTip("删除选中的行")
        self._del_row_btn.clicked.connect(self._on_delete_rows)
        tools.addWidget(self._add_row_btn)
        tools.addWidget(self._del_row_btn)

        self._add_col_btn = QPushButton("加列")
        self._add_col_btn.setToolTip("追加新列")
        self._add_col_btn.clicked.connect(self._on_add_column)
        self._rename_col_btn = QPushButton("重命名列")
        self._rename_col_btn.setToolTip("重命名所选列")
        self._rename_col_btn.clicked.connect(self._on_rename_column)
        self._drop_col_btn = QPushButton("删列")
        self._drop_col_btn.setToolTip("删除所选列")
        self._drop_col_btn.clicked.connect(self._on_drop_column)
        self._clear_btn = QPushButton("清空表")
        self._clear_btn.setToolTip("删除当前表全部行（可撤销）")
        self._clear_btn.clicked.connect(self._on_clear_table)
        tools.addWidget(self._add_col_btn)
        tools.addWidget(self._rename_col_btn)
        tools.addWidget(self._drop_col_btn)
        tools.addWidget(self._clear_btn)
        tools.addStretch(1)
        root.addLayout(tools)

        # ---------- 编辑表格 ----------
        body = card()
        body_layout = QVBoxLayout(body)
        body_layout.setContentsMargins(0, 0, 0, 0)
        body_layout.setSpacing(0)
        self._view = QTableView()
        self._view.setObjectName("editView")
        self._view.setModel(self._edit.edit_model())
        self._view.setAlternatingRowColors(True)
        self._view.verticalHeader().setVisible(False)
        self._view.horizontalHeader().setStretchLastSection(True)
        body_layout.addWidget(self._view)
        self._empty = caption_label("选择数据表后开始编辑")
        self._empty.setAlignment(Qt.AlignCenter)
        self._empty.setMinimumHeight(160)
        self._empty.setVisible(True)
        self._view.setVisible(False)
        body_layout.addWidget(self._empty)
        root.addWidget(body, stretch=1)

        # ---------- 分页条 ----------
        pager = QHBoxLayout()
        pager.setSpacing(SPACING_SM)
        self._prev_btn = QPushButton("上一页")
        self._prev_btn.clicked.connect(self._on_prev_page)
        self._next_btn = QPushButton("下一页")
        self._next_btn.clicked.connect(self._on_next_page)
        self._page_label = caption_label("")
        pager.addWidget(self._prev_btn)
        pager.addWidget(self._next_btn)
        pager.addWidget(self._page_label, stretch=1)
        root.addLayout(pager)

        # ---------- 信号装配 ----------
        self._edit.tables_model().modelReset.connect(self._on_tables_reset)
        self._edit.table_loaded.connect(self._on_table_loaded)  # pyrefly: ignore [missing-attribute]
        self._edit.undo_changed.connect(self._update_actions)  # pyrefly: ignore [missing-attribute]
        self._edit.error_raised.connect(self._toast.show_error)  # pyrefly: ignore [missing-attribute]
        self._ws.current_changed.connect(self._on_workspace_changed)  # pyrefly: ignore [missing-attribute]
        # 模型整页重载（撤销/结构变化）时保持视图选中（行列操作连续进行）
        edit_model = self._edit.edit_model()
        edit_model.modelAboutToBeReset.connect(self._save_selection)
        edit_model.modelReset.connect(self._restore_selection)

        self._saved_selection: tuple[int, int] | None = None
        self._on_workspace_changed()

        # Ctrl+C 复制选区为 TSV 文本（可直接粘贴到 Excel/文本编辑器）
        self._copy_shortcut = QShortcut(QKeySequence.Copy, self._view)
        self._copy_shortcut.activated.connect(self._on_copy)

    # ----------------------------- 工作区与表 -----------------------------

    def _on_workspace_changed(self) -> None:
        """工作区切换：重载表列表。."""
        self._edit.load_tables(self._ws.current_workspace_path())
        self._on_tables_reset()

    def showEvent(self, event: QShowEvent) -> None:
        """页面可见时重载表列表（对齐 QML onVisibleChanged）。."""
        super().showEvent(event)
        if self._ws.current_workspace_path():
            self._edit.load_tables(self._ws.current_workspace_path())
            self._on_tables_reset()

    def _on_tables_reset(self) -> None:
        """表列表重置：刷新下拉并校准当前选择。."""
        model = self._edit.tables_model()
        tables = [model.table_at(row) or "" for row in range(model.rowCount())]
        self._table_combo.blockSignals(True)
        self._table_combo.clear()
        self._table_combo.addItems(tables)
        current = self._edit.current_table()
        if current in tables:
            self._table_combo.setCurrentText(current)
        self._table_combo.blockSignals(False)
        if current and current not in tables:
            # 当前表已不存在（如被删除）
            self._table_combo.blockSignals(True)
            self._table_combo.setCurrentIndex(-1)
            self._table_combo.blockSignals(False)
        self._update_actions()

    def _on_table_activated(self, index: int) -> None:
        """选择数据表进入编辑。."""
        table = self._table_combo.itemText(index)
        if table:
            self._edit.open_table(table)

    def _on_table_loaded(self) -> None:
        """表数据重载：刷新分页信息与空态。."""
        has_table = self._edit.has_table()
        self._view.setVisible(has_table)
        self._empty.setVisible(not has_table)
        if has_table:
            from finaldb.core.editing.service import PAGE_SIZE

            total = self._edit.total_rows()
            pages = max(1, (total + PAGE_SIZE - 1) // PAGE_SIZE)
            self._page_label.setText(f"第 {self._edit.current_page() + 1}/{pages} 页 · 共 {total} 行")
        else:
            self._page_label.setText("")
        self._update_actions()

    # ----------------------------- 行操作 -----------------------------

    def _on_add_row(self) -> None:
        """追加空行。."""
        self._edit.add_row()

    def _on_delete_rows(self) -> None:
        """删除选中行（多选）。"""
        rows = sorted({index.row() for index in self._view.selectionModel().selectedRows()})
        rowids = self._edit.edit_model().rowids_of(rows)
        if not rowids:
            self._toast.show_message("请先选中要删除的行")
            return
        answer = QMessageBox.question(
            self,
            "删除行",
            f"确定删除选中的 {len(rowids)} 行？（可撤销）",
            QMessageBox.Yes | QMessageBox.No,
        )
        if answer == QMessageBox.Yes:
            self._edit.delete_rows(rowids)

    def _on_clear_table(self) -> None:
        """清空当前表全部行（确认，可撤销）。."""
        if not self._edit.has_table():
            return
        table = self._edit.current_table()
        total = self._edit.total_rows()
        answer = QMessageBox.question(
            self,
            "清空表",
            f"确定删除表「{table}」全部 {total} 行？（可撤销）",
            QMessageBox.Yes | QMessageBox.No,
        )
        if answer == QMessageBox.Yes:
            self._edit.clear_table()

    def _on_copy(self) -> None:
        """复制选区为 TSV 文本（Ctrl+C，可直接粘贴到 Excel/文本）。."""
        indexes = self._view.selectionModel().selectedIndexes()
        if not indexes:
            return
        model = self._edit.edit_model()
        cells: dict[tuple[int, int], str] = {}
        for index in indexes:
            value = model.data(index)
            cells[(index.row(), index.column())] = "" if value is None else str(value)
        rows = sorted({r for r, _ in cells})
        cols = sorted({c for _, c in cells})
        text = "\n".join("\t".join(cells.get((r, c), "") for c in cols) for r in rows)
        QApplication.clipboard().setText(text)

    # ----------------------------- 列操作 -----------------------------

    def _on_add_column(self) -> None:
        """追加新列（输入列名）。."""
        if not self._edit.has_table():
            self._toast.show_message("请先选择数据表")
            return
        name, ok = QInputDialog.getText(self, "新增列", "列名（仅字母/数字/下划线/中文）:")
        if not ok or not name.strip():
            return
        self._edit.add_column(name.strip())

    def _selected_column(self) -> str:
        """当前选中列名（列头或单元格所在列）。"""
        index = self._view.currentIndex()
        model = self._edit.edit_model()
        if not index.isValid():
            return ""
        columns_count = model.columnCount()
        col = index.column()
        if not (0 <= col < columns_count):
            return ""
        return str(model.headerData(col, Qt.Horizontal) or "")

    def _save_selection(self) -> None:
        """模型重置前记录当前选中单元格。."""
        index = self._view.currentIndex()
        self._saved_selection = (index.row(), index.column()) if index.isValid() else None

    def _restore_selection(self) -> None:
        """模型重载后恢复选中单元格（行列仍在有效范围内时）。"""
        if self._saved_selection is None:
            return
        row, col = self._saved_selection
        self._saved_selection = None
        model = self._edit.edit_model()
        if 0 <= row < model.rowCount() and 0 <= col < model.columnCount():
            self._view.setCurrentIndex(model.index(row, col))

    def _on_rename_column(self) -> None:
        """重命名所选列。"""
        old = self._selected_column()
        if not old:
            self._toast.show_message("请先选中要重命名的列")
            return
        new, ok = QInputDialog.getText(self, "重命名列", f"「{old}」的新列名:", text=old)
        if not ok or not new.strip() or new.strip() == old:
            return
        self._edit.rename_column(old, new.strip())

    def _on_drop_column(self) -> None:
        """删除所选列（确认）。"""
        column = self._selected_column()
        if not column:
            self._toast.show_message("请先选中要删除的列")
            return
        answer = QMessageBox.question(
            self,
            "删除列",
            f"确定删除列「{column}」及其全部数据？（可撤销）",
            QMessageBox.Yes | QMessageBox.No,
        )
        if answer == QMessageBox.Yes:
            self._edit.drop_column(column)

    # ----------------------------- 分页 -----------------------------

    def _on_prev_page(self) -> None:
        """上一页。."""
        self._edit.goto_page(self._edit.current_page() - 1)

    def _on_next_page(self) -> None:
        """下一页。."""
        self._edit.goto_page(self._edit.current_page() + 1)

    # ----------------------------- 状态 -----------------------------

    def _update_actions(self) -> None:
        """按会话状态刷新按钮可用态与撤销重做提示。."""
        has_table = self._edit.has_table()
        self._undo_btn.setEnabled(has_table and self._edit.can_undo())
        self._redo_btn.setEnabled(has_table and self._edit.can_redo())
        self._add_row_btn.setEnabled(has_table)
        self._del_row_btn.setEnabled(has_table)
        self._add_col_btn.setEnabled(has_table)
        self._rename_col_btn.setEnabled(has_table)
        self._drop_col_btn.setEnabled(has_table)
        self._clear_btn.setEnabled(has_table)
        self._prev_btn.setEnabled(has_table and self._edit.current_page() > 0)
        from finaldb.core.editing.service import PAGE_SIZE

        self._next_btn.setEnabled(has_table and (self._edit.current_page() + 1) * PAGE_SIZE < self._edit.total_rows())
        if self._undo_btn.isEnabled():
            self._undo_btn.setToolTip(f"撤销: {self._edit.undo_label()}")
        else:
            self._undo_btn.setToolTip("撤销上一步编辑")
        if self._redo_btn.isEnabled():
            self._redo_btn.setToolTip(f"重做: {self._edit.redo_label()}")
        else:
            self._redo_btn.setToolTip("重做被撤销的编辑")
