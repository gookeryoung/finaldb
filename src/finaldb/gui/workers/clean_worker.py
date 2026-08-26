"""清洗后台 Worker：在工作线程执行 core 清洗落库，信号回报结果。."""

from __future__ import annotations

import sqlite3
from collections.abc import Sequence
from pathlib import Path

from PySide2.QtCore import QObject, Signal, Slot

from finaldb.core.cleaning.rules import CleanRule
from finaldb.core.cleaning.service import clean_table
from finaldb.core.exceptions import FinaldbError
from finaldb.core.storage.database import connect

__all__ = ["CleanWorker"]


class CleanWorker(QObject):
    """清洗落库 Worker（源表不动，结果写入新表）。."""

    finished = Signal(str)
    failed = Signal(str)

    def __init__(
        self,
        db_path: str,
        table: str,
        rules: Sequence[CleanRule],
        target: str = "",
        parent: object | None = None,
    ) -> None:
        """保存清洗参数。

        :param db_path: 工作区数据库文件路径
        :param table: 源表名
        :param rules: 清洗规则列表
        :param target: 新表名（空串自动命名）
        """
        super().__init__(parent)
        self._db_path = db_path
        self._table = table
        self._rules = list(rules)
        self._target = target

    @Slot()  # pyrefly: ignore [not-callable]
    def run(self) -> None:
        """执行清洗并发出完成/失败信号（工作线程内运行）。"""
        try:
            conn: sqlite3.Connection = connect(Path(self._db_path))
            try:
                summary = clean_table(conn, self._table, self._rules, target=self._target)
            finally:
                conn.close()
        except (OSError, ValueError, FinaldbError) as exc:
            self.failed.emit(f"清洗失败: {exc}")  # pyrefly: ignore [missing-attribute]
            return
        message = f"已生成新表 {summary.target}（{summary.rows_written} 行）"
        self.finished.emit(message)  # pyrefly: ignore [missing-attribute]
