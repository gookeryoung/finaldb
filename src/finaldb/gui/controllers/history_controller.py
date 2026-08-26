"""历史控制器：桥接 core 版本控制服务与 QML 版本历史页。

职责：快照列表加载、提交/回滚/对比的后台调度与 diff 文本暴露。
"""

from __future__ import annotations

from pathlib import Path

from PySide2.QtCore import Property, QObject, QThread, Signal, Slot

from finaldb.core.versioning import list_snapshots
from finaldb.gui.models.snapshot_model import SnapshotListModel
from finaldb.gui.workers.history_worker import HistoryJob, HistoryWorker

__all__ = ["HistoryController"]

# Worker 失败消息前缀（history_worker 约定）
_FAIL_PREFIX = "版本操作失败"


class HistoryController(QObject):
    """版本历史页控制器（QML 绑定 ``HistoryCtrl``）。."""

    busy_changed = Signal()
    diff_changed = Signal()
    applied = Signal(str)
    failed = Signal(str)
    error_raised = Signal(str)

    def __init__(self, parent: QObject | None = None) -> None:
        """初始化控制器与快照模型。."""
        super().__init__(parent)
        self._model = SnapshotListModel(self)
        self._diff_text = ""
        self._busy = False
        self._action = ""
        self._thread: QThread | None = None
        self._worker: HistoryWorker | None = None

    # ----------------------------- 属性 -----------------------------

    @Property(QObject, notify=busy_changed)  # pyrefly: ignore [not-callable]
    def snapshotsModel(self) -> SnapshotListModel:
        """快照列表模型。."""
        return self._model

    def _get_diff_text(self) -> str:
        """最近一次对比的 diff 文本。."""
        return self._diff_text

    diffText = Property(str, _get_diff_text, notify=diff_changed)

    def _get_busy(self) -> bool:
        """是否正在执行后台版本操作。."""
        return self._busy

    busy = Property(bool, _get_busy, notify=busy_changed)

    # ----------------------------- 槽 -----------------------------

    @Slot(str)  # pyrefly: ignore [not-callable]
    def load_history(self, workspace_path: str) -> None:
        """加载工作区快照列表。."""
        if not workspace_path:
            self._model.reload([])
            return
        self._model.reload(list_snapshots(Path(workspace_path)))

    @Slot(str, str)  # pyrefly: ignore [not-callable]
    def commit(self, workspace_path: str, message: str) -> None:
        """后台提交当前数据为快照。"""
        self._start(HistoryWorker(workspace_path, HistoryJob("commit", message=message)))

    @Slot(str, str)  # pyrefly: ignore [not-callable]
    def restore(self, workspace_path: str, ref: str) -> None:
        """后台回滚到指定快照。"""
        if not ref:
            self.error_raised.emit("请先选择要回滚的快照")  # pyrefly: ignore [missing-attribute]
            return
        self._start(HistoryWorker(workspace_path, HistoryJob("restore", ref=ref)))

    @Slot(str, str, str)  # pyrefly: ignore [not-callable]
    def diff(self, workspace_path: str, ref_old: str, ref_new: str) -> None:
        """后台对比两快照并更新 diffText。"""
        if not ref_old or not ref_new:
            self.error_raised.emit("请先选择两个快照进行对比")  # pyrefly: ignore [missing-attribute]
            return
        self._start(HistoryWorker(workspace_path, HistoryJob("diff", ref_old=ref_old, ref_new=ref_new)))

    # 同步版本（测试用：在当前线程执行 Worker.run）

    def commit_sync(self, workspace_path: str, message: str) -> None:
        """同步提交快照（测试用）。"""
        self._run_sync(HistoryWorker(workspace_path, HistoryJob("commit", message=message)))

    def restore_sync(self, workspace_path: str, ref: str) -> None:
        """同步回滚（测试用）。"""
        self._run_sync(HistoryWorker(workspace_path, HistoryJob("restore", ref=ref)))

    def diff_sync(self, workspace_path: str, ref_old: str, ref_new: str) -> None:
        """同步对比（测试用）。"""
        self._run_sync(HistoryWorker(workspace_path, HistoryJob("diff", ref_old=ref_old, ref_new=ref_new)))

    # ----------------------------- 内部 -----------------------------

    def _start(self, worker: HistoryWorker) -> None:
        """启动后台线程执行 Worker。"""
        if self._busy:
            self.error_raised.emit("已有任务进行中，请稍候")  # pyrefly: ignore [missing-attribute]
            return
        self._set_busy(True)
        self._action = worker.action
        self._thread = QThread(self)
        self._worker = worker
        self._worker.moveToThread(self._thread)
        self._thread.started.connect(self._worker.run)
        self._worker.finished.connect(self._on_done)  # pyrefly: ignore [missing-attribute]
        self._worker.failed.connect(self._on_done)  # pyrefly: ignore [missing-attribute]
        self._worker.finished.connect(self._thread.quit)  # pyrefly: ignore [missing-attribute]
        self._worker.failed.connect(self._thread.quit)  # pyrefly: ignore [missing-attribute]
        self._thread.finished.connect(self._worker.deleteLater)
        self._thread.finished.connect(self._thread.deleteLater)
        self._thread.finished.connect(self._on_thread_finished)
        self._thread.start()

    def _run_sync(self, worker: HistoryWorker) -> None:
        """当前线程执行 Worker（测试用）。"""
        self._action = worker.action
        worker.finished.connect(self._on_done)  # pyrefly: ignore [missing-attribute]
        worker.failed.connect(self._on_done)  # pyrefly: ignore [missing-attribute]
        worker.run()

    def _on_done(self, message: str) -> None:
        """完成/失败回调：按操作类型更新 diff 文本并转发消息。."""
        if message.startswith(_FAIL_PREFIX):
            self.failed.emit(message)  # pyrefly: ignore [missing-attribute]
            return
        if self._action == "diff":
            self._set_diff(message)
        self.applied.emit(message)  # pyrefly: ignore [missing-attribute]

    def _on_thread_finished(self) -> None:
        """后台线程退出：清理引用并解除忙状态。"""
        self._thread = None
        self._worker = None
        self._set_busy(False)

    def _set_diff(self, text: str) -> None:
        """更新 diff 文本。."""
        if self._diff_text != text:
            self._diff_text = text
            self.diff_changed.emit()  # pyrefly: ignore [missing-attribute]

    def _set_busy(self, value: bool) -> None:
        """更新忙状态。."""
        if self._busy != value:
            self._busy = value
            self.busy_changed.emit()  # pyrefly: ignore [missing-attribute]
