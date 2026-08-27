"""编辑控制器：桥接 core 编辑服务与 Widgets 编辑页。

职责：编辑会话管理（打开表/分页）、命令分发（单元格/行/列）、
撤销重做状态推送。界面只连接本控制器的信号与调用其方法。
"""

from __future__ import annotations

from pathlib import Path

from PySide2.QtCore import QObject, Signal

from finaldb.core.editing import EditService
from finaldb.gui.models.edit_model import EditableTableModel
from finaldb.gui.models.table_model import TableListModel

__all__ = ["EditingController"]


class EditingController(QObject):
    """数据编辑控制器（同步命令，编辑页使用）。."""

    table_loaded = Signal()
    data_changed = Signal()
    undo_changed = Signal()
    error_raised = Signal(str)

    def __init__(self, parent: QObject | None = None) -> None:
        """初始化控制器与模型。."""
        super().__init__(parent)
        self._service: EditService | None = None
        self._model = EditableTableModel(self)
        self._tables_model = TableListModel(self)
        self._table = ""
        self._workspace_path = ""
        self._page = 0
        self._total_rows = 0
        # 单元格编辑委托：模型 setData → 本控制器 set_cell
        self._model.set_cell_callback(self._on_model_set_cell)

    # ----------------------------- 只读访问 -----------------------------

    def edit_model(self) -> EditableTableModel:
        """编辑表格模型。."""
        return self._model

    def tables_model(self) -> TableListModel:
        """可编辑表列表模型。."""
        return self._tables_model

    def current_table(self) -> str:
        """当前编辑的表名（空串表示未打开）。."""
        return self._table

    def current_page(self) -> int:
        """当前页码（0 起）。."""
        return self._page

    def total_rows(self) -> int:
        """当前表总行数。."""
        return self._total_rows

    def can_undo(self) -> bool:
        """是否有可撤销命令。."""
        return self._service.can_undo() if self._service else False

    def can_redo(self) -> bool:
        """是否有可重做命令。."""
        return self._service.can_redo() if self._service else False

    def undo_label(self) -> str:
        """撤销栈顶命令描述。."""
        return self._service.undo_label() if self._service else ""

    def redo_label(self) -> str:
        """重做栈顶命令描述。."""
        return self._service.redo_label() if self._service else ""

    def has_table(self) -> bool:
        """是否打开了编辑中的表。."""
        return self._table != ""

    # ----------------------------- 会话管理 -----------------------------

    def load_tables(self, workspace_path: str) -> None:
        """重载工作区可编辑表列表。."""
        from finaldb.core.storage.database import connect, table_infos

        self._workspace_path = workspace_path
        if not workspace_path:
            self._tables_model.reload([])
            self._close_table()
            return
        conn = connect(Path(workspace_path) / "data.db")
        try:
            infos = table_infos(conn)
        finally:
            conn.close()
        self._tables_model.reload([(i.name, i.row_count) for i in infos])

    def open_table(self, table: str) -> None:
        """打开指定表进入编辑会话（重置页码与撤销栈）。."""
        if not self._workspace_path:
            self.error_raised.emit("未选择工作区")  # pyrefly: ignore [missing-attribute]
            return
        self._service = EditService(Path(self._workspace_path) / "data.db")
        self._table = table
        self._page = 0
        self._reload_page()
        self.table_loaded.emit()  # pyrefly: ignore [missing-attribute]
        self.undo_changed.emit()  # pyrefly: ignore [missing-attribute]

    def goto_page(self, page: int) -> None:
        """跳转页码（钳制到有效范围）。."""
        if not self._service or not self._table:
            return
        from finaldb.core.editing.service import PAGE_SIZE

        max_page = max(0, (self._total_rows - 1) // PAGE_SIZE)
        self._page = max(0, min(page, max_page))
        self._reload_page()
        self.table_loaded.emit()  # pyrefly: ignore [missing-attribute]

    # ----------------------------- 编辑命令 -----------------------------

    def set_cell(self, table: str, rowid: int, column: str, text: str) -> None:
        """修改单元格（异常转错误信号；命令式入口，重载当前页）。."""
        if self._service is None:
            return
        try:
            self._service.set_cell(table, rowid, column, text)
        except ValueError as exc:
            self.error_raised.emit(str(exc))  # pyrefly: ignore [missing-attribute]
            return
        self._reload_page()
        self.data_changed.emit()  # pyrefly: ignore [missing-attribute]
        self.undo_changed.emit()  # pyrefly: ignore [missing-attribute]

    def add_row(self) -> None:
        """当前表追加空行。."""
        if self._service is None or not self._table:
            return
        try:
            self._service.add_row(self._table)
        except ValueError as exc:
            self.error_raised.emit(str(exc))  # pyrefly: ignore [missing-attribute]
            return
        self._after_row_change()

    def delete_rows(self, rowids: list[int]) -> None:
        """删除指定行。."""
        if self._service is None or not self._table:
            return
        try:
            self._service.delete_rows(self._table, rowids)
        except ValueError as exc:
            self.error_raised.emit(str(exc))  # pyrefly: ignore [missing-attribute]
            return
        self._after_row_change()

    def add_column(self, column: str, sql_type: str = "TEXT") -> None:
        """追加新列。."""
        if self._service is None or not self._table:
            return
        try:
            self._service.add_column(self._table, column, sql_type)
        except ValueError as exc:
            self.error_raised.emit(str(exc))  # pyrefly: ignore [missing-attribute]
            return
        self._after_structure_change()

    def rename_column(self, old: str, new: str) -> None:
        """重命名列。."""
        if self._service is None or not self._table:
            return
        try:
            self._service.rename_column(self._table, old, new)
        except ValueError as exc:
            self.error_raised.emit(str(exc))  # pyrefly: ignore [missing-attribute]
            return
        self._after_structure_change()

    def drop_column(self, column: str) -> None:
        """删除列。."""
        if self._service is None or not self._table:
            return
        try:
            self._service.drop_column(self._table, column)
        except ValueError as exc:
            self.error_raised.emit(str(exc))  # pyrefly: ignore [missing-attribute]
            return
        self._after_structure_change()

    # ----------------------------- 撤销 / 重做 -----------------------------

    def undo(self) -> None:
        """撤销栈顶命令。."""
        if self._service is None:
            return
        try:
            self._service.undo()
        except ValueError as exc:
            self.error_raised.emit(str(exc))  # pyrefly: ignore [missing-attribute]
            return
        self._reload_page()
        self.table_loaded.emit()  # pyrefly: ignore [missing-attribute]
        self.undo_changed.emit()  # pyrefly: ignore [missing-attribute]

    def redo(self) -> None:
        """重做栈顶命令。."""
        if self._service is None:
            return
        try:
            self._service.redo()
        except ValueError as exc:
            self.error_raised.emit(str(exc))  # pyrefly: ignore [missing-attribute]
            return
        self._reload_page()
        self.table_loaded.emit()  # pyrefly: ignore [missing-attribute]
        self.undo_changed.emit()  # pyrefly: ignore [missing-attribute]

    # ----------------------------- 内部 -----------------------------

    def _on_model_set_cell(self, rowid: int, column: str, text: str) -> bool:
        """模型 setData 委托入口（成功返回 True 由模型更新缓存）。"""
        if self._service is None or not self._table:
            return False
        try:
            self._service.set_cell(self._table, rowid, column, text)
        except ValueError as exc:
            self.error_raised.emit(str(exc))  # pyrefly: ignore [missing-attribute]
            return False
        self.undo_changed.emit()  # pyrefly: ignore [missing-attribute]
        return True

    def _reload_page(self) -> None:
        """从服务重载当前页到模型。."""
        if self._service is None or not self._table:
            return
        columns, rows, total = self._service.fetch_page(self._table, self._page)
        self._total_rows = total
        self._model.reset_data(columns, rows)

    def _after_row_change(self) -> None:
        """行数变化：刷新行数与表列表，重载当前页。."""
        self._reload_page()
        self.table_loaded.emit()  # pyrefly: ignore [missing-attribute]
        self.undo_changed.emit()  # pyrefly: ignore [missing-attribute]
        if self._workspace_path:
            self.load_tables(self._workspace_path)

    def _after_structure_change(self) -> None:
        """列结构变化：刷新表列表并重载当前页。."""
        self._after_row_change()

    def _close_table(self) -> None:
        """关闭编辑会话。."""
        self._service = None
        self._table = ""
        self._page = 0
        self._total_rows = 0
        self._model.reset_data([], [])
        self.table_loaded.emit()  # pyrefly: ignore [missing-attribute]
        self.undo_changed.emit()  # pyrefly: ignore [missing-attribute]
