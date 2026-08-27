"""表预览控制器：加载指定工作区表的前 N 行到预览模型。."""

from __future__ import annotations

from pathlib import Path

from PySide2.QtCore import QObject, Signal

from finaldb.core.storage.database import fetch_preview
from finaldb.gui.models.table_model import TablePreviewModel

__all__ = ["PreviewController"]

# 预览行数上限
_PREVIEW_LIMIT = 200


class PreviewController(QObject):
    """表数据预览控制器（首页预览表格使用）。."""

    table_changed = Signal()

    def __init__(self, parent: QObject | None = None) -> None:
        """初始化控制器与预览模型。."""
        super().__init__(parent)
        self._model = TablePreviewModel(self)
        self._table_name = ""

    # ----------------------------- 只读访问 -----------------------------

    def preview_model(self) -> TablePreviewModel:
        """预览表格模型。."""
        return self._model

    def table_name(self) -> str:
        """当前预览的表名（空串表示未加载）。."""
        return self._table_name

    # ----------------------------- 操作 -----------------------------

    def load_table(self, workspace_path: str, table: str) -> None:
        """加载工作区指定表的前 200 行。

        :param workspace_path: 工作区目录路径
        :param table: 表名
        """
        from finaldb.core.storage.database import connect

        conn = connect(Path(workspace_path) / "data.db")
        try:
            columns, rows = fetch_preview(conn, table, limit=_PREVIEW_LIMIT)
        finally:
            conn.close()
        self._model.reset_data(columns, rows)
        self._table_name = table
        self.table_changed.emit()  # pyrefly: ignore [missing-attribute]

    def clear(self) -> None:
        """清空预览。"""
        self._model.reset_data([], [])
        self._table_name = ""
        self.table_changed.emit()  # pyrefly: ignore [missing-attribute]
