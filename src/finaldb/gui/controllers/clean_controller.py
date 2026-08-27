"""清洗控制器：桥接 core 清洗引擎与 Widgets 数据整理页。

职责：表/列加载、规则增删管理、预览（含统计报告）、后台清洗落库。
界面只连接本控制器的信号与调用其方法，不直接触碰 core。
"""

from __future__ import annotations

from pathlib import Path

from PySide2.QtCore import QObject, QThread, Signal

from finaldb.core.cleaning.engine import apply_rules
from finaldb.core.cleaning.rules import CaseMode, CleanRule, RuleKind
from finaldb.core.exceptions import CleanError
from finaldb.core.storage.database import column_infos, connect, fetch_preview, table_infos
from finaldb.gui.models.clean_models import CleanRuleListModel, StringListModel
from finaldb.gui.models.table_model import TableListModel, TablePreviewModel
from finaldb.gui.workers.clean_worker import CleanWorker

__all__ = ["CleanController"]

# 预览行数上限（与预览控制器一致）
_PREVIEW_LIMIT = 200


class CleanController(QObject):
    """数据整理页控制器。."""

    columns_changed = Signal()
    report_changed = Signal()
    busy_changed = Signal()
    applied = Signal(str)
    failed = Signal(str)
    error_raised = Signal(str)

    def __init__(self, parent: QObject | None = None) -> None:
        """初始化控制器与各模型。."""
        super().__init__(parent)
        self._tables_model = TableListModel(self)
        self._columns_model = StringListModel(self)
        self._rules_model = CleanRuleListModel(self)
        self._preview_model = TablePreviewModel(self)
        self._report_text = ""
        self._busy = False
        self._thread: QThread | None = None
        self._worker: CleanWorker | None = None

    # ----------------------------- 只读访问 -----------------------------

    def tables_model(self) -> TableListModel:
        """表列表模型。."""
        return self._tables_model

    def columns_model(self) -> StringListModel:
        """列名列表模型。."""
        return self._columns_model

    def rules_model(self) -> CleanRuleListModel:
        """规则列表模型。."""
        return self._rules_model

    def preview_model(self) -> TablePreviewModel:
        """清洗预览表格模型。."""
        return self._preview_model

    def report_text(self) -> str:
        """预览统计报告文本（多行）。."""
        return self._report_text

    def is_busy(self) -> bool:
        """是否正在执行后台清洗。."""
        return self._busy

    # ----------------------------- 操作 -----------------------------

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

    def load_columns(self, workspace_path: str, table: str) -> None:
        """加载指定表的列名列表。."""
        if not workspace_path or not table:
            self._columns_model.reload([])
            return
        conn = connect(Path(workspace_path) / "data.db")
        try:
            infos = column_infos(conn, table)
        finally:
            conn.close()
        self._columns_model.reload([c.name for c in infos])

    def preview(self, workspace_path: str, table: str) -> None:
        """对表前 200 行应用当前规则并刷新预览与统计。."""
        rules = self._rules_model.rules()
        if not rules:
            self.error_raised.emit("请先添加清洗规则")  # pyrefly: ignore [missing-attribute]
            return
        conn = connect(Path(workspace_path) / "data.db")
        try:
            columns, rows = fetch_preview(conn, table, limit=_PREVIEW_LIMIT)
        finally:
            conn.close()
        try:
            transformed, report = apply_rules(columns, rows, rules)
        except CleanError as exc:
            self.error_raised.emit(str(exc))  # pyrefly: ignore [missing-attribute]
            return
        cleaned = list(transformed)
        self._preview_model.reset_data(columns, cleaned)
        header = f"预览统计（前 {min(_PREVIEW_LIMIT, len(cleaned))} 行）"
        self._report_text = header + "\n" + "\n".join(report.format_lines(rules))
        self.report_changed.emit()  # pyrefly: ignore [missing-attribute]

    def add_rule(self, kind: str, column: str, value: str, replacement: str, case_mode: str) -> None:
        """构造并追加一条规则（参数非法即报错）。."""
        if not column:
            self.error_raised.emit("请选择目标列")  # pyrefly: ignore [missing-attribute]
            return
        try:
            rule_kind = RuleKind(kind)
            mode = CaseMode(case_mode) if case_mode else CaseMode.LOWER
        except ValueError:
            self.error_raised.emit(f"未知规则类型: {kind}")  # pyrefly: ignore [missing-attribute]
            return
        rule = CleanRule(
            kind=rule_kind,
            column=column,
            value=value,
            replacement=replacement,
            case_mode=mode,
        )
        if rule_kind in (RuleKind.REPLACE, RuleKind.FILL_MISSING) and not value:
            self.error_raised.emit("该规则需要填写参数值")  # pyrefly: ignore [missing-attribute]
            return
        self._rules_model.append_rule(rule)

    def remove_rule(self, row: int) -> None:
        """删除指定行的规则。."""
        self._rules_model.remove_row(row)

    def clear_rules(self) -> None:
        """清空全部规则与预览。."""
        self._rules_model.clear()
        self._preview_model.reset_data([], [])
        self._report_text = ""
        self.report_changed.emit()  # pyrefly: ignore [missing-attribute]

    def apply(self, workspace_path: str, table: str, target: str) -> None:
        """后台清洗落库（源表不动，结果写入新表）。"""
        if self._busy:
            self.error_raised.emit("已有任务进行中，请稍候")  # pyrefly: ignore [missing-attribute]
            return
        rules = self._rules_model.rules()
        if not rules:
            self.error_raised.emit("请先添加清洗规则")  # pyrefly: ignore [missing-attribute]
            return
        self._set_busy(True)
        self._thread = QThread(self)
        self._worker = CleanWorker(str(Path(workspace_path) / "data.db"), table, rules, target.strip())
        self._worker.moveToThread(self._thread)
        self._thread.started.connect(self._worker.run)
        self._worker.finished.connect(self._on_apply_done)  # pyrefly: ignore [missing-attribute]
        self._worker.failed.connect(self._on_apply_done)  # pyrefly: ignore [missing-attribute]
        self._worker.finished.connect(self._thread.quit)  # pyrefly: ignore [missing-attribute]
        self._worker.failed.connect(self._thread.quit)  # pyrefly: ignore [missing-attribute]
        self._thread.finished.connect(self._worker.deleteLater)
        self._thread.finished.connect(self._thread.deleteLater)
        self._thread.finished.connect(self._on_thread_finished)
        self._thread.start()

    def apply_sync(self, workspace_path: str, table: str, target: str) -> None:
        """同步清洗（测试用：在当前线程执行 Worker.run）。"""
        rules = self._rules_model.rules()
        if not rules:
            self.error_raised.emit("请先添加清洗规则")  # pyrefly: ignore [missing-attribute]
            return
        worker = CleanWorker(str(Path(workspace_path) / "data.db"), table, rules, target.strip())
        worker.finished.connect(self._on_apply_done)  # pyrefly: ignore [missing-attribute]
        worker.failed.connect(self._on_apply_done)  # pyrefly: ignore [missing-attribute]
        worker.run()

    # ----------------------------- 内部 -----------------------------

    def _on_apply_done(self, message: str) -> None:
        """清洗完成/失败回调：转发消息。

        Worker 约定：失败消息以「清洗失败」开头。
        """
        if message.startswith("清洗失败"):
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
