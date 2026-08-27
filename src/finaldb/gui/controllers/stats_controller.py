"""统计控制器：桥接 core 统计分析与 Widgets 统计页。

职责：工作区表分布概览（表数/行数/列数/体积）与单表列级统计加载。
界面只连接本控制器的信号与调用其方法。
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

from PySide2.QtCore import QObject, Signal

from finaldb.core.stats import column_stats as _column_stats
from finaldb.core.stats import format_size, workspace_overview
from finaldb.core.storage.database import connect, table_infos
from finaldb.gui.models.column_stat_model import ColumnStatModel
from finaldb.gui.models.stats_model import TableStatModel

__all__ = ["StatsController"]

# 未选择工作区时的摘要文案
_EMPTY_SUMMARY = "未选择工作区（请先在数据页选择）"


class StatsController(QObject):
    """统计页控制器。."""

    stats_changed = Signal()
    table_stats_changed = Signal()

    def __init__(self, parent: QObject | None = None) -> None:
        """初始化控制器与模型。."""
        super().__init__(parent)
        self._model = TableStatModel(self)
        self._column_model = ColumnStatModel(self)
        self._summary = _EMPTY_SUMMARY

    # ----------------------------- 只读访问 -----------------------------

    def stats_model(self) -> TableStatModel:
        """表统计列表模型。."""
        return self._model

    def table_stats_model(self) -> ColumnStatModel:
        """列统计表模型。."""
        return self._column_model

    def summary_text(self) -> str:
        """统计摘要文本。."""
        return self._summary

    def table_names(self) -> list[str]:
        """当前工作区全部表名（表选择下拉数据源）。."""
        names: list[str] = []
        for row in range(self._model.rowCount()):
            stat = self._model.stat_at(row)
            names.append(stat.name if stat else "")
        return names

    # ----------------------------- 操作 -----------------------------

    def load_stats(self, workspace_path: str) -> None:
        """加载工作区全部表的统计（表数、行数、列数、体积）。."""
        if not workspace_path:
            self._model.reload([])
            self._column_model.reload([])
            self._set_summary(_EMPTY_SUMMARY)
            return
        db_path = Path(workspace_path) / "data.db"
        if not db_path.is_file():
            self._model.reload([])
            self._column_model.reload([])
            self._set_summary("当前工作区暂无数据（导入后自动生成）")
            return
        try:
            conn = connect(db_path)
            try:
                infos = table_infos(conn)
                overview = workspace_overview(conn, db_path)
            finally:
                conn.close()
        except (OSError, sqlite3.Error) as exc:
            self._model.reload([])
            self._column_model.reload([])
            self._set_summary(f"读取统计失败: {exc}")
            return
        self._model.reload(infos)
        self._set_summary(
            f"共 {overview.table_count} 张表 · {overview.total_rows} 行 · "
            f"{overview.total_columns} 列 · {format_size(overview.db_bytes)}"
        )

    def load_table_stats(self, workspace_path: str, table: str) -> None:
        """加载单表列级统计（未选工作区/表时清空模型）。."""
        if not workspace_path or not table:
            self._column_model.reload([])
            self.table_stats_changed.emit()  # pyrefly: ignore [missing-attribute]
            return
        db_path = Path(workspace_path) / "data.db"
        try:
            conn = connect(db_path)
            try:
                stats = _column_stats(conn, table)
            finally:
                conn.close()
        except (OSError, sqlite3.Error):
            self._column_model.reload([])
            self.table_stats_changed.emit()  # pyrefly: ignore [missing-attribute]
            return
        self._column_model.reload(stats)
        self.table_stats_changed.emit()  # pyrefly: ignore [missing-attribute]

    # ----------------------------- 内部 -----------------------------

    def _set_summary(self, text: str) -> None:
        """更新摘要文本。."""
        if self._summary != text:
            self._summary = text
            self.stats_changed.emit()  # pyrefly: ignore [missing-attribute]
