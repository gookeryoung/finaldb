"""数据编辑面板：可编辑表格 + 行列操作 + 分页 + 撤销重做。

作为数据页的右侧面板嵌入：表选择由外部（数据页表列表）驱动，
面板只负责编辑会话的展示与命令入口。
"""

from __future__ import annotations

from PySide2.QtCore import QSize, Qt
from PySide2.QtGui import QKeySequence
from PySide2.QtWidgets import (
    QApplication,
    QFrame,
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
from finaldb.gui.theme import SPACING_SM, ThemeManager
from finaldb.gui.widgets.common import caption_label, card
from finaldb.gui.widgets.icons import build_icon
from finaldb.gui.widgets.toast import Toast

__all__ = ["EditPanel"]


def _tool_button(tip: str, variant: str = "secondary") -> QPushButton:
    """纯图标工具按钮工厂：无文字，悬浮提示说明用途。

    Args:
        tip: 悬浮提示（承担原文字按钮的语义说明）
        variant: 操作分级（secondary 描边 / danger 危险 / 留空为主操作实心）

    Returns:
        配置好的按钮（图标由面板统一按主题装配）
    """
    btn = QPushButton()
    btn.setToolTip(tip)
    btn.setIconSize(QSize(18, 18))
    btn.setProperty("iconButton", True)
    if variant:
        btn.setProperty("variant", variant)
    return btn


def _tool_separator() -> QFrame:
    """工具栏分组竖分隔线。."""
    line = QFrame()
    line.setObjectName("toolSeparator")
    line.setFixedSize(1, 22)
    return line


class EditPanel(QWidget):
    """数据编辑面板：工具栏（撤销/行列操作）+ 编辑表格 + 分页条。."""

    def __init__(
        self,
        theme: ThemeManager,
        editing_ctrl: EditingController,
        parent: QWidget | None = None,
    ) -> None:
        """初始化面板并装配控制器信号。

        Args:
            theme: 主题管理器
            editing_ctrl: 编辑控制器
            parent: 父部件
        """
        super().__init__(parent)
        self._theme = theme
        self._edit = editing_ctrl
        self._toast = Toast(self, theme)

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(SPACING_SM)

        # ---------- 工具行：撤销重做 | 行操作 | 列操作 | 危险操作 ----------
        tools = QHBoxLayout()
        tools.setSpacing(SPACING_SM)

        self._undo_btn = _tool_button("撤销上一步编辑")
        self._undo_btn.clicked.connect(self._edit.undo)
        self._redo_btn = _tool_button("重做被撤销的编辑")
        self._redo_btn.clicked.connect(self._edit.redo)
        tools.addWidget(self._undo_btn)
        tools.addWidget(self._redo_btn)

        tools.addWidget(_tool_separator())

        self._add_row_btn = _tool_button("在表末尾追加一行", variant="")
        self._add_row_btn.clicked.connect(self._on_add_row)
        self._del_row_btn = _tool_button("删除选中的行", variant="danger")
        self._del_row_btn.clicked.connect(self._on_delete_rows)
        tools.addWidget(self._add_row_btn)
        tools.addWidget(self._del_row_btn)

        tools.addWidget(_tool_separator())

        self._add_col_btn = _tool_button("追加新列")
        self._add_col_btn.clicked.connect(self._on_add_column)
        self._rename_col_btn = _tool_button("重命名所选列")
        self._rename_col_btn.clicked.connect(self._on_rename_column)
        self._drop_col_btn = _tool_button("删除所选列", variant="danger")
        self._drop_col_btn.clicked.connect(self._on_drop_column)
        tools.addWidget(self._add_col_btn)
        tools.addWidget(self._rename_col_btn)
        tools.addWidget(self._drop_col_btn)

        tools.addWidget(_tool_separator())

        self._clear_btn = _tool_button("清空表（删除全部行，可撤销）", variant="danger")
        self._clear_btn.clicked.connect(self._on_clear_table)
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
        # 行号列：编辑定位行更直观（按页内偏移显示，跟随分页刷新）
        self._view.verticalHeader().setVisible(True)
        self._view.horizontalHeader().setStretchLastSection(True)
        body_layout.addWidget(self._view)
        self._empty = caption_label("选择左侧数据表后开始编辑")
        self._empty.setObjectName("editEmpty")
        self._empty.setAlignment(Qt.AlignCenter)
        self._empty.setMinimumHeight(200)
        self._empty.setVisible(True)
        self._view.setVisible(False)
        body_layout.addWidget(self._empty)
        root.addWidget(body, stretch=1)

        # ---------- 分页条（居中） ----------
        pager = QHBoxLayout()
        pager.setSpacing(SPACING_SM)
        self._prev_btn = _tool_button("上一页")
        self._prev_btn.clicked.connect(self._on_prev_page)
        self._next_btn = _tool_button("下一页")
        self._next_btn.clicked.connect(self._on_next_page)
        self._page_label = caption_label("")
        pager.addStretch(1)
        pager.addWidget(self._prev_btn)
        pager.addWidget(self._page_label)
        pager.addWidget(self._next_btn)
        pager.addStretch(1)
        root.addLayout(pager)

        # ---------- 信号装配 ----------
        self._edit.table_loaded.connect(self._on_table_loaded)  # pyrefly: ignore [missing-attribute]
        self._edit.undo_changed.connect(self._update_actions)  # pyrefly: ignore [missing-attribute]
        self._edit.error_raised.connect(self._toast.show_error)  # pyrefly: ignore [missing-attribute]
        # 工具栏/分页按钮 → 图标名映射（颜色按按钮分级随主题重建）
        self._icon_buttons: list[tuple[QPushButton, str]] = [
            (self._undo_btn, "undo"),
            (self._redo_btn, "redo"),
            (self._add_row_btn, "add_row"),
            (self._del_row_btn, "del_row"),
            (self._add_col_btn, "add_col"),
            (self._rename_col_btn, "rename_col"),
            (self._drop_col_btn, "del_col"),
            (self._clear_btn, "clear_table"),
            (self._prev_btn, "prev_page"),
            (self._next_btn, "next_page"),
        ]
        self._apply_icons()
        self._theme.theme_changed.connect(self._apply_icons)  # pyrefly: ignore [missing-attribute]
        # 模型整页重载（撤销/结构变化）时保持视图选中（行列操作连续进行）
        edit_model = self._edit.edit_model()
        edit_model.modelAboutToBeReset.connect(self._save_selection)
        edit_model.modelReset.connect(self._restore_selection)

        self._saved_selection: tuple[int, int] | None = None
        self._on_table_loaded()
        self._update_actions()

        # Ctrl+C 复制选区为 TSV 文本（可直接粘贴到 Excel/文本编辑器）
        self._copy_shortcut = QShortcut(QKeySequence.Copy, self._view)
        self._copy_shortcut.activated.connect(self._on_copy)

    # ----------------------------- 对外 API -----------------------------

    def open_table(self, table: str) -> None:
        """打开指定表进入编辑会话（表由数据页表列表选择）。."""
        self._edit.open_table(table)

    def refresh_tables(self, workspace_path: str) -> None:
        """重载工作区表列表（工作区切换/导入后调用）。."""
        self._edit.load_tables(workspace_path)

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

    # ----------------------------- 图标 -----------------------------

    def _apply_icons(self) -> None:
        """按当前主题为全部工具按钮重建图标。

        图标颜色与按钮分级一致：主操作取主色底上的前景色、
        secondary 取正文色、danger 取危险色；主题切换时整体重绘。
        """
        for btn, name in self._icon_buttons:
            variant = str(btn.property("variant") or "")
            if variant == "danger":
                color = self._theme.color("danger")
            elif variant == "secondary":
                color = self._theme.color("text_primary")
            else:
                color = self._theme.color("text_on_primary")
            btn.setIcon(build_icon(name, color))

    # ----------------------------- 状态 -----------------------------

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
