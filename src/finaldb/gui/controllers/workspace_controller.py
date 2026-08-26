"""工作区控制器：桥接 core 工作区服务与 QML 界面。

职责：工作区增删查、当前工作区选择、数据导入调度（QThread Worker）。
界面只连接本控制器的信号与槽，不直接触碰 core。
"""

from __future__ import annotations

import time
from pathlib import Path

from PySide2.QtCore import Property, QObject, QThread, Signal, Slot

from finaldb.core.exceptions import WorkspaceError
from finaldb.core.storage.database import table_infos
from finaldb.core.workspace import Workspace, WorkspaceManager
from finaldb.gui.models.table_model import TableListModel
from finaldb.gui.models.workspace_model import WorkspaceListModel
from finaldb.gui.workers.import_worker import ImportWorker

__all__ = ["WorkspaceController"]


class WorkspaceController(QObject):
    """工作区列表 + 当前工作区 + 导入调度控制器。."""

    workspaces_changed = Signal()
    current_changed = Signal()
    busy_changed = Signal()
    import_finished = Signal(str)
    import_failed = Signal(str)
    error_raised = Signal(str)

    def __init__(self, root: Path | None = None, parent: QObject | None = None) -> None:
        """初始化控制器与模型。

        :param root: 工作区根目录（None 用默认；测试注入临时目录）
        """
        super().__init__(parent)
        self._manager = WorkspaceManager(root)
        self._model = WorkspaceListModel(self)
        self._table_model = TableListModel(self)
        self._current: Workspace | None = None
        self._busy = False
        self._thread: QThread | None = None
        self._worker: ImportWorker | None = None
        self.refresh()

    # ----------------------------- 属性 -----------------------------

    def _workspace_root(self) -> str:
        """工作区根目录（CONSTANT）。."""
        return str(self._manager.root)

    workspaceRoot = Property(str, _workspace_root, constant=True)

    def _get_current_name(self) -> str:
        """当前工作区名（未选择为空串）。."""
        return self._current.name if self._current else ""

    def _get_current_path(self) -> str:
        """当前工作区目录（未选择为空串）。."""
        return str(self._current.path) if self._current else ""

    currentWorkspace = Property(str, _get_current_name, notify=current_changed)
    currentWorkspacePath = Property(str, _get_current_path, notify=current_changed)

    def _get_busy(self) -> bool:
        """是否正在执行后台任务。."""
        return self._busy

    busy = Property(bool, _get_busy, notify=busy_changed)

    # 模型对象恒定：notify 仅满足 QML 绑定要求，重读返回同一引用
    @Property(QObject, notify=workspaces_changed)  # pyrefly: ignore [not-callable]
    def model(self) -> WorkspaceListModel:
        """工作区列表模型。."""
        return self._model

    @Property(QObject, notify=current_changed)  # pyrefly: ignore [not-callable]
    def tableModel(self) -> TableListModel:
        """当前工作区表列表模型。."""
        return self._table_model

    # ----------------------------- 槽 -----------------------------

    @Slot()  # pyrefly: ignore [not-callable]
    def refresh(self) -> None:
        """刷新工作区列表（保持当前选择有效）。"""
        self._model.reload(self._manager.list())
        if self._current is not None and not self._current.db_path.parent.exists():
            self._current = None
            self._reload_tables()
            self.current_changed.emit()  # pyrefly: ignore [missing-attribute]
        self.workspaces_changed.emit()  # pyrefly: ignore [missing-attribute]

    @Slot(str)  # pyrefly: ignore [not-callable]
    def create_workspace(self, name: str) -> None:
        """创建工作区并选中。"""
        try:
            ws = self._manager.create(name)
        except (WorkspaceError, OSError) as exc:
            self.error_raised.emit(str(exc))  # pyrefly: ignore [missing-attribute]
            return
        self._current = ws
        self._reload_tables()
        self.refresh()
        self.current_changed.emit()  # pyrefly: ignore [missing-attribute]

    @Slot(str)  # pyrefly: ignore [not-callable]
    def select_workspace(self, name: str) -> None:
        """按名称选择当前工作区。."""
        for meta in self._manager.list():
            if meta.name == name:
                self._current = self._manager.open(meta.path)
                self._reload_tables()
                self.current_changed.emit()  # pyrefly: ignore [missing-attribute]
                return
        self.error_raised.emit(f"工作区不存在: {name}")  # pyrefly: ignore [missing-attribute]

    @Slot(str)  # pyrefly: ignore [not-callable]
    def delete_workspace(self, name: str) -> None:
        """删除工作区（若为当前工作区则清空选择）。"""
        for meta in self._manager.list():
            if meta.name == name:
                try:
                    self._manager.delete(meta.path)
                except (WorkspaceError, OSError) as exc:
                    self.error_raised.emit(str(exc))  # pyrefly: ignore [missing-attribute]
                    return
                if self._current is not None and self._current.name == name:
                    self._current = None
                    self._reload_tables()
                    self.current_changed.emit()  # pyrefly: ignore [missing-attribute]
                self.refresh()
                return
        self.error_raised.emit(f"工作区不存在: {name}")  # pyrefly: ignore [missing-attribute]

    @Slot(str)  # pyrefly: ignore [not-callable]
    def import_file(self, url_or_path: str) -> None:
        """后台导入数据文件到当前工作区（file:/// URL 或本地路径）。"""
        if self._current is None:
            self.error_raised.emit("请先选择工作区")  # pyrefly: ignore [missing-attribute]
            return
        if self._busy:
            self.error_raised.emit("已有任务进行中，请稍候")  # pyrefly: ignore [missing-attribute]
            return
        local = _to_local_path(url_or_path)
        if not local:
            self.error_raised.emit(f"无法解析文件路径: {url_or_path}")  # pyrefly: ignore [missing-attribute]
            return
        self._set_busy(True)
        self._thread = QThread(self)
        self._worker = ImportWorker(str(self._current.db_path), local)
        self._worker.moveToThread(self._thread)
        self._thread.started.connect(self._worker.run)
        self._worker.finished.connect(self._on_import_done)  # pyrefly: ignore [missing-attribute]
        self._worker.failed.connect(self._on_import_done)  # pyrefly: ignore [missing-attribute]
        self._worker.finished.connect(self._thread.quit)  # pyrefly: ignore [missing-attribute]
        self._worker.failed.connect(self._thread.quit)  # pyrefly: ignore [missing-attribute]
        self._thread.finished.connect(self._worker.deleteLater)
        self._thread.finished.connect(self._thread.deleteLater)
        self._thread.finished.connect(self._on_thread_finished)
        self._thread.start()

    def import_file_sync(self, url_or_path: str) -> None:
        """同步导入（测试用：在当前线程执行 Worker.run）。"""
        if self._current is None:
            self.error_raised.emit("请先选择工作区")  # pyrefly: ignore [missing-attribute]
            return
        local = _to_local_path(url_or_path)
        if not local:
            self.error_raised.emit(f"无法解析文件路径: {url_or_path}")  # pyrefly: ignore [missing-attribute]
            return
        worker = ImportWorker(str(self._current.db_path), local)
        worker.finished.connect(self._on_import_done)  # pyrefly: ignore [missing-attribute]
        worker.failed.connect(self._on_import_done)  # pyrefly: ignore [missing-attribute]
        worker.run()

    # ----------------------------- 内部 -----------------------------

    def _on_import_done(self, message: str) -> None:
        """导入完成/失败回调：转发消息并刷新列表。

        Worker 约定：失败消息以「导入失败」开头。
        """
        if message.startswith("导入失败"):
            self.import_failed.emit(message)  # pyrefly: ignore [missing-attribute]
        else:
            self.import_finished.emit(message)  # pyrefly: ignore [missing-attribute]
        self._reload_tables()
        self.refresh()

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

    def _reload_tables(self) -> None:
        """重载当前工作区的表列表。"""
        if self._current is None:
            self._table_model.reload([])
            return
        conn = self._current.connect()
        try:
            infos = table_infos(conn)
        finally:
            conn.close()
        self._table_model.reload([(t.name, t.row_count) for t in infos])


def _to_local_path(url_or_path: str) -> str:
    """把 QML FileDialog 的 file:/// URL 转为本地路径。

    :param url_or_path: URL 或本地路径字符串
    :return: 本地路径（无法解析返回空串）
    """
    text = url_or_path.strip()
    if not text:
        return ""
    if text.startswith("file:///"):
        return text[len("file:///") :]
    if text.startswith("file://"):
        return text[len("file://") :]
    return text


def format_timestamp(ts: float) -> str:
    """时间戳格式化为界面可读文本（无效值显示占位符）。

    :param ts: Unix 时间戳
    :return: ``YYYY-MM-DD HH:MM`` 文本
    """
    if ts <= 0:
        return "—"
    return time.strftime("%Y-%m-%d %H:%M", time.localtime(ts))
