"""合并后台 Worker：在工作线程执行 union/dedup/join，信号回报结果。."""

from __future__ import annotations

import sqlite3
from pathlib import Path

from PySide2.QtCore import QObject, Signal, Slot

from finaldb.core.exceptions import FinaldbError
from finaldb.core.merge import JoinSpec, MergeJob, MergeSummary
from finaldb.core.merge.service import dedup_table, join_tables, union_tables
from finaldb.core.storage.database import connect

__all__ = ["MergeWorker"]

# join 模式下键列缺失时的兜底空连接参数
_EMPTY_JOIN = JoinSpec(left="", right="", left_key="", right_key="")


class MergeWorker(QObject):
    """合并/去重/连接 Worker（源表不动，结果写入新表）。."""

    finished = Signal(str)
    failed = Signal(str)

    def __init__(self, db_path: str, job: MergeJob, parent: object | None = None) -> None:
        """保存合并参数。

        :param db_path: 工作区数据库文件路径
        :param job: 合并任务描述（kind 决定字段含义）
        :param parent: Qt 父对象
        """
        super().__init__(parent)
        self._db_path = db_path
        self._job = job

    @Slot()  # pyrefly: ignore [not-callable]
    def run(self) -> None:
        """执行合并并发出完成/失败信号（工作线程内运行）。"""
        try:
            conn: sqlite3.Connection = connect(Path(self._db_path))
            try:
                summary = self._execute(conn)
            finally:
                conn.close()
        except (OSError, ValueError, FinaldbError) as exc:
            self.failed.emit(f"合并失败: {exc}")  # pyrefly: ignore [missing-attribute]
            return
        self.finished.emit(f"{summary.detail}，新表 {summary.target}")  # pyrefly: ignore [missing-attribute]

    def _execute(self, conn: sqlite3.Connection) -> MergeSummary:
        """按任务 kind 分发到 core 合并服务。."""
        job = self._job
        if job.kind == "union":
            return union_tables(conn, job.tables, target=job.target)
        if job.kind == "dedup":
            table = job.tables[0] if job.tables else ""
            return dedup_table(conn, table, keys=job.keys, target=job.target)
        if job.kind == "join":
            return join_tables(conn, job.join or _EMPTY_JOIN, target=job.target)
        raise ValueError(f"未知合并类型: {job.kind}")
