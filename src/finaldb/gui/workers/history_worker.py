"""版本控制后台 Worker：在工作线程执行提交/回滚/对比，信号回报结果。."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from PySide2.QtCore import QObject, Signal, Slot

from finaldb.core.exceptions import FinaldbError
from finaldb.core.versioning import commit_snapshot, restore_snapshot, snapshot_diff

__all__ = ["HistoryJob", "HistoryWorker"]

# 失败消息前缀约定（控制器据此区分 finished/failed）
_FAIL_PREFIX = "版本操作失败"


@dataclass(frozen=True)
class HistoryJob:
    """版本操作参数（``action`` ∈ commit/restore/diff）。."""

    action: str
    message: str = ""
    ref: str = ""
    ref_old: str = ""
    ref_new: str = ""


class HistoryWorker(QObject):
    """快照提交/回滚/对比 Worker。."""

    finished = Signal(str)
    failed = Signal(str)

    def __init__(self, ws_path: str, job: HistoryJob, parent: object | None = None) -> None:
        """保存操作参数。

        :param ws_path: 工作区目录路径
        :param job: 版本操作参数（操作类型 + 提交说明/引用）
        """
        super().__init__(parent)
        self._ws_path = ws_path
        self._job = job

    @property
    def action(self) -> str:
        """操作类型（commit/restore/diff）。."""
        return self._job.action

    @Slot()  # pyrefly: ignore [not-callable]
    def run(self) -> None:
        """执行操作并发出完成/失败信号（工作线程内运行）。"""
        try:
            result = self._execute()
        except (OSError, ValueError, FinaldbError) as exc:
            self.failed.emit(f"{_FAIL_PREFIX}: {exc}")  # pyrefly: ignore [missing-attribute]
            return
        self.finished.emit(result)  # pyrefly: ignore [missing-attribute]

    def _execute(self) -> str:
        """按 action 分发到 core 版本控制服务。."""
        ws = Path(self._ws_path)
        job = self._job
        if job.action == "commit":
            info = commit_snapshot(ws, job.message)
            return f"已提交快照 {info.short_id}: {info.message}"
        if job.action == "restore":
            info = restore_snapshot(ws, job.ref)
            return f"已回滚到快照 {info.short_id}: {info.message}"
        if job.action == "diff":
            return snapshot_diff(ws, job.ref_old, job.ref_new)
        raise ValueError(f"未知版本操作: {job.action}")
