"""导入后台 Worker：在工作线程执行 core 导入，信号回报结果。

禁止在此操作 GUI 部件，只发信号。
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

from PySide2.QtCore import QObject, Signal, Slot

from finaldb.core.exceptions import FinaldbError, VersionError
from finaldb.core.importers.service import import_into_workspace
from finaldb.core.storage.database import connect
from finaldb.core.versioning import commit_snapshot, has_changes

__all__ = ["ImportWorker"]

# 预览/导入的空结果摘要
_EMPTY_SUMMARY = "未导入任何表"


class ImportWorker(QObject):
    """数据导入 Worker（导入目标为指定工作区的 data.db）。."""

    finished = Signal(str)
    failed = Signal(str)

    def __init__(self, db_path: str, file_path: str, parent: object | None = None) -> None:
        """保存导入目标与来源。

        :param db_path: 工作区数据库文件路径
        :param file_path: 待导入数据文件路径
        """
        super().__init__(parent)
        self._db_path = db_path
        self._file_path = file_path

    @Slot()  # pyrefly: ignore [not-callable]
    def run(self) -> None:
        """执行导入并发出完成/失败信号（工作线程内运行）。"""
        try:
            conn: sqlite3.Connection = connect(Path(self._db_path))
            try:
                results = import_into_workspace(conn, Path(self._file_path))
            finally:
                conn.close()
        except (OSError, ValueError, FinaldbError) as exc:
            self.failed.emit(f"导入失败: {exc}")  # pyrefly: ignore [missing-attribute]
            return
        if not results:
            self.finished.emit(_EMPTY_SUMMARY)  # pyrefly: ignore [missing-attribute]
            return
        # 导入成功后自动打快照（无变化时静默跳过，快照失败不阻断导入结果）
        self._auto_snapshot()
        summary = "、".join(f"{r.table}({r.rows} 行)" for r in results)
        self.finished.emit(f"已导入 {summary}")  # pyrefly: ignore [missing-attribute]

    def _auto_snapshot(self) -> None:
        """导入后自动提交快照（尽力而为，失败静默）。."""
        ws_path = Path(self._db_path).parent
        try:
            if has_changes(ws_path):
                commit_snapshot(ws_path, f"导入 {Path(self._file_path).name}")
        except (OSError, VersionError):
            pass
