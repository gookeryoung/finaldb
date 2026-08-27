"""统计控制器：桥接 core 表元数据与 Widgets 统计页。."""

from __future__ import annotations

import sqlite3
from pathlib import Path

from PySide2.QtCore import QObject, Signal

from finaldb.core.storage.database import connect, table_infos
from finaldb.gui.models.stats_model import TableStatModel

__all__ = ["StatsController"]

# 未选择工作区时的摘要文案
_EMPTY_SUMMARY = "未选择工作区（请先在数据源页选择）"


class StatsController(QObject):
    """统计页控制器。."""

    stats_changed = Signal()

    def __init__(self, parent: QObject | None = None) -> None:
        """初始化控制器与统计模型。."""
        super().__init__(parent)
        self._model = TableStatModel(self)
        self._summary = _EMPTY_SUMMARY

    # ----------------------------- 只读访问 -----------------------------

    def stats_model(self) -> TableStatModel:
        """表统计列表模型。."""
        return self._model

    def summary_text(self) -> str:
        """统计摘要文本。."""
        return self._summary

    # ----------------------------- 操作 -----------------------------

    def load_stats(self, workspace_path: str) -> None:
        """加载工作区全部表的统计（表数、行数、列数）。."""
        if not workspace_path:
            self._model.reload([])
            self._set_summary(_EMPTY_SUMMARY)
            return
        db_path = Path(workspace_path) / "data.db"
        if not db_path.is_file():
            self._model.reload([])
            self._set_summary("当前工作区暂无数据（导入后自动生成）")
            return
        try:
            conn = connect(db_path)
            try:
                infos = table_infos(conn)
            finally:
                conn.close()
        except (OSError, sqlite3.Error) as exc:
            self._model.reload([])
            self._set_summary(f"读取统计失败: {exc}")
            return
        self._model.reload(infos)
        total_rows = sum(info.row_count for info in infos)
        self._set_summary(f"共 {len(infos)} 张表，{total_rows} 行数据")

    # ----------------------------- 内部 -----------------------------

    def _set_summary(self, text: str) -> None:
        """更新摘要文本。."""
        if self._summary != text:
            self._summary = text
            self.stats_changed.emit()  # pyrefly: ignore [missing-attribute]
