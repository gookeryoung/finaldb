"""合并控制器：桥接 core 合并服务与 QML 合并去重页。

职责：表/列加载、union/dedup/join 三种合并模式的后台调度。
QML 侧多值（表列表、键列列表）用单元分隔符拼接的字符串传递。
"""

from __future__ import annotations

from pathlib import Path

from PySide2.QtCore import Property, QObject, QThread, Signal, Slot

from finaldb.core.merge import JoinSpec, MergeJob
from finaldb.core.storage.database import column_infos, connect, table_infos
from finaldb.gui.models.clean_models import StringListModel
from finaldb.gui.models.table_model import TableListModel
from finaldb.gui.workers.merge_worker import MergeWorker

__all__ = ["MergeController"]

# 多值分隔符（\x1f 控制字符不可能出现在合法标识符中，避免拆分歧义）
_UNIT_SEP = "\x1f"


class MergeController(QObject):
    """合并去重页控制器（QML 绑定 ``MergeCtrl``）。."""

    busy_changed = Signal()
    applied = Signal(str)
    failed = Signal(str)
    error_raised = Signal(str)

    def __init__(self, parent: QObject | None = None) -> None:
        """初始化控制器与各模型。."""
        super().__init__(parent)
        self._tables_model = TableListModel(self)
        self._dedup_columns_model = StringListModel(self)
        self._left_columns_model = StringListModel(self)
        self._right_columns_model = StringListModel(self)
        self._busy = False
        self._thread: QThread | None = None
        self._worker: MergeWorker | None = None

    # ----------------------------- 属性 -----------------------------

    @Property(QObject, notify=busy_changed)  # pyrefly: ignore [not-callable]
    def tablesModel(self) -> TableListModel:
        """表列表模型。."""
        return self._tables_model

    @Property(QObject, notify=busy_changed)  # pyrefly: ignore [not-callable]
    def dedupColumnsModel(self) -> StringListModel:
        """去重页键列候选模型。."""
        return self._dedup_columns_model

    @Property(QObject, notify=busy_changed)  # pyrefly: ignore [not-callable]
    def leftColumnsModel(self) -> StringListModel:
        """连接页左表键列候选模型。."""
        return self._left_columns_model

    @Property(QObject, notify=busy_changed)  # pyrefly: ignore [not-callable]
    def rightColumnsModel(self) -> StringListModel:
        """连接页右表键列候选模型。."""
        return self._right_columns_model

    def _get_busy(self) -> bool:
        """是否正在执行后台合并。."""
        return self._busy

    busy = Property(bool, _get_busy, notify=busy_changed)

    # ----------------------------- 槽 -----------------------------

    @Slot(str)  # pyrefly: ignore [not-callable]
    def load_tables(self, workspace_path: str) -> None:
        """加载工作区的表列表。."""
        if not workspace_path:
            self._tables_model.reload([])
            return
        conn = connect(Path(workspace_path) / "data.db")
        try:
            infos = table_infos(conn)
        finally:
            conn.close()
        self._tables_model.reload([(t.name, t.row_count) for t in infos])

    @Slot(str, str)  # pyrefly: ignore [not-callable]
    def load_columns(self, workspace_path: str, table: str) -> None:
        """加载去重页指定表的列名。."""
        self._dedup_columns_model.reload(self._columns_of(workspace_path, table))

    @Slot(str, str, str)  # pyrefly: ignore [not-callable]
    def load_join_columns(self, workspace_path: str, left: str, right: str) -> None:
        """加载连接页左右表的列名。."""
        self._left_columns_model.reload(self._columns_of(workspace_path, left))
        self._right_columns_model.reload(self._columns_of(workspace_path, right))

    @Slot(str, str, str)  # pyrefly: ignore [not-callable]
    def apply_union(self, workspace_path: str, tables_joined: str, target: str) -> None:
        """后台纵向合并多表。."""
        tables = [t for t in tables_joined.split(_UNIT_SEP) if t]
        self._start(
            MergeWorker(
                self._db_path(workspace_path),
                MergeJob(kind="union", tables=tuple(tables), target=target.strip()),
            )
        )

    @Slot(str, str, str, str)  # pyrefly: ignore [not-callable]
    def apply_dedup(self, workspace_path: str, table: str, keys_joined: str, target: str) -> None:
        """后台表去重（keys 为空 = 全行去重）。"""
        keys = [k for k in keys_joined.split(_UNIT_SEP) if k]
        self._start(
            MergeWorker(
                self._db_path(workspace_path),
                MergeJob(kind="dedup", tables=(table,), keys=tuple(keys), target=target.strip()),
            )
        )

    @Slot(str, str)  # pyrefly: ignore [not-callable]
    def apply_join(self, workspace_path: str, params_joined: str) -> None:
        """后台两表按键连接。

        :param params_joined: 单元分隔符拼接的 6 段参数
            （左表、右表、左键列、右键列、连接方式、新表名）
        """
        self._start(MergeWorker(self._db_path(workspace_path), self._join_job(params_joined)))

    # 同步版本（测试用：在当前线程执行 Worker.run）

    def apply_union_sync(self, workspace_path: str, tables_joined: str, target: str) -> None:
        """同步纵向合并（测试用）。"""
        tables = [t for t in tables_joined.split(_UNIT_SEP) if t]
        self._run_sync(
            MergeWorker(
                self._db_path(workspace_path),
                MergeJob(kind="union", tables=tuple(tables), target=target.strip()),
            )
        )

    def apply_dedup_sync(self, workspace_path: str, table: str, keys_joined: str, target: str) -> None:
        """同步去重（测试用）。"""
        keys = [k for k in keys_joined.split(_UNIT_SEP) if k]
        self._run_sync(
            MergeWorker(
                self._db_path(workspace_path),
                MergeJob(kind="dedup", tables=(table,), keys=tuple(keys), target=target.strip()),
            )
        )

    def apply_join_sync(self, workspace_path: str, params_joined: str) -> None:
        """同步连接（测试用）。"""
        self._run_sync(MergeWorker(self._db_path(workspace_path), self._join_job(params_joined)))

    # ----------------------------- 内部 -----------------------------

    def _join_job(self, params_joined: str) -> MergeJob:
        """把分隔符拼接的连接参数解析为 MergeJob。"""
        parts = params_joined.split(_UNIT_SEP)
        while len(parts) < 6:
            parts.append("")
        left, right, left_key, right_key, how, target = parts[:6]
        return MergeJob(
            kind="join",
            join=JoinSpec(left=left, right=right, left_key=left_key, right_key=right_key, how=how),
            target=target.strip(),
        )

    def _db_path(self, workspace_path: str) -> str:
        """工作区数据库文件路径。"""
        return str(Path(workspace_path) / "data.db")

    def _columns_of(self, workspace_path: str, table: str) -> list[str]:
        """读取指定表列名（表为空返回空列表）。"""
        if not workspace_path or not table:
            return []
        conn = connect(Path(workspace_path) / "data.db")
        try:
            infos = column_infos(conn, table)
        finally:
            conn.close()
        return [c.name for c in infos]

    def _start(self, worker: MergeWorker) -> None:
        """启动后台线程执行 Worker。"""
        if self._busy:
            self.error_raised.emit("已有任务进行中，请稍候")  # pyrefly: ignore [missing-attribute]
            return
        self._set_busy(True)
        self._thread = QThread(self)
        self._worker = worker
        self._worker.moveToThread(self._thread)
        self._thread.started.connect(self._worker.run)
        self._worker.finished.connect(self._on_merge_done)  # pyrefly: ignore [missing-attribute]
        self._worker.failed.connect(self._on_merge_done)  # pyrefly: ignore [missing-attribute]
        self._worker.finished.connect(self._thread.quit)  # pyrefly: ignore [missing-attribute]
        self._worker.failed.connect(self._thread.quit)  # pyrefly: ignore [missing-attribute]
        self._thread.finished.connect(self._worker.deleteLater)
        self._thread.finished.connect(self._thread.deleteLater)
        self._thread.finished.connect(self._on_thread_finished)
        self._thread.start()

    def _run_sync(self, worker: MergeWorker) -> None:
        """当前线程执行 Worker（测试用）。"""
        worker.finished.connect(self._on_merge_done)  # pyrefly: ignore [missing-attribute]
        worker.failed.connect(self._on_merge_done)  # pyrefly: ignore [missing-attribute]
        worker.run()

    def _on_merge_done(self, message: str) -> None:
        """合并完成/失败回调：转发消息。

        Worker 约定：失败消息以「合并失败」开头。
        """
        if message.startswith("合并失败"):
            self.failed.emit(message)  # pyrefly: ignore [missing-attribute]
        else:
            self.applied.emit(message)  # pyrefly: ignore [missing-attribute]

    def _on_thread_finished(self) -> None:
        """后台线程退出：清理引用并解除忙状态。"""
        self._thread = None
        self._worker = None
        self._set_busy(False)

    def _set_busy(self, value: bool) -> None:
        """更新忙状态。"""
        if self._busy != value:
            self._busy = value
            self.busy_changed.emit()  # pyrefly: ignore [missing-attribute]
