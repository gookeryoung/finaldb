"""清洗控制器测试：表/列加载、规则增删、预览统计、同步/异步落库。."""

from __future__ import annotations

import time
from pathlib import Path

import pytest
from PySide2.QtCore import Qt
from PySide2.QtGui import QGuiApplication

from finaldb.core.cleaning.rules import CleanRule, RuleKind
from finaldb.gui.controllers.clean_controller import CleanController
from finaldb.gui.models.clean_models import CleanRuleListModel, StringListModel

pytestmark = pytest.mark.gui

# 记录信号的收集器
_SIGNALS: list[tuple[str, str]] = []


def _on_error(msg: str) -> None:
    """error_raised 信号收集器。."""
    _SIGNALS.append(("error", msg))


def _on_applied(msg: str) -> None:
    """applied 信号收集器。."""
    _SIGNALS.append(("applied", msg))


def _on_failed(msg: str) -> None:
    """failed 信号收集器。."""
    _SIGNALS.append(("failed", msg))


@pytest.fixture()
def clean_setup(qapp: QGuiApplication, tmp_path: Path) -> tuple[CleanController, Path]:
    """构造带脏数据表的临时工作区与控制器。."""
    from finaldb.core.storage.database import connect

    ws = tmp_path / "ws"
    ws.mkdir()
    conn = connect(ws / "data.db")
    conn.execute('CREATE TABLE "t" ("name" TEXT, "age" TEXT)')
    conn.executemany(
        'INSERT INTO "t" VALUES (?, ?)',
        [(" 甲 ", "30"), ("乙", None), (None, "25")],
    )
    conn.commit()
    conn.close()

    ctrl = CleanController()
    ctrl.load_tables(str(ws))
    return ctrl, ws


def _connect_signals(ctrl: CleanController) -> list[tuple[str, str]]:
    """挂接错误/完成信号到收集器并清空旧记录。."""
    _SIGNALS.clear()
    ctrl.error_raised.connect(_on_error)  # pyrefly: ignore [missing-attribute]
    ctrl.applied.connect(_on_applied)  # pyrefly: ignore [missing-attribute]
    ctrl.failed.connect(_on_failed)  # pyrefly: ignore [missing-attribute]
    return _SIGNALS


def test_load_tables(clean_setup: tuple[CleanController, Path]) -> None:
    """load_tables 加载表列表。."""
    ctrl, _ws = clean_setup
    assert ctrl.tablesModel.rowCount() == 1
    assert ctrl.tablesModel.table_at(0) == "t"


def test_load_tables_empty_path(clean_setup: tuple[CleanController, Path]) -> None:
    """空路径清空表列表。."""
    ctrl, _ws = clean_setup
    ctrl.load_tables("")
    assert ctrl.tablesModel.rowCount() == 0


def test_load_columns(clean_setup: tuple[CleanController, Path]) -> None:
    """load_columns 加载列名列表。."""
    ctrl, ws = clean_setup
    ctrl.load_columns(str(ws), "t")
    assert ctrl.columnsModel.rowCount() == 2
    assert ctrl.columnsModel.item_at(0) == "name"
    assert ctrl.columnsModel.item_at(1) == "age"
    # 空参数清空
    ctrl.load_columns("", "")
    assert ctrl.columnsModel.rowCount() == 0


def test_add_and_remove_rules(clean_setup: tuple[CleanController, Path]) -> None:
    """add_rule 追加规则、remove_rule 删除、clear_rules 清空。."""
    ctrl, _ws = clean_setup
    signals = _connect_signals(ctrl)
    ctrl.add_rule("trim", "name", "", "", "")
    ctrl.add_rule("to_number", "age", "", "", "")
    assert ctrl.rulesModel.rowCount() == 2
    rule = ctrl.rulesModel.rule_at(0)
    assert rule is not None and rule.column == "name"
    ctrl.remove_rule(0)
    assert ctrl.rulesModel.rowCount() == 1
    ctrl.remove_rule(99)  # 越界静默
    assert ctrl.rulesModel.rowCount() == 1
    ctrl.clear_rules()
    assert ctrl.rulesModel.rowCount() == 0
    assert ctrl.previewModel.rowCount() == 0
    assert ctrl.reportText == ""
    assert signals == []


def test_add_rule_invalid_params(clean_setup: tuple[CleanController, Path]) -> None:
    """非法规则参数发 error_raised 且不追加。."""
    ctrl, _ws = clean_setup
    signals = _connect_signals(ctrl)
    # 未知类型
    ctrl.add_rule("nope", "name", "", "", "")
    # 空列
    ctrl.add_rule("trim", "", "", "", "")
    # REPLACE 缺参数
    ctrl.add_rule("replace", "name", "", "x", "")
    # FILL 缺参数
    ctrl.add_rule("fill_missing", "name", "", "", "")
    assert ctrl.rulesModel.rowCount() == 0
    assert len(signals) == 4
    assert all(kind == "error" for kind, _msg in signals)


def test_add_rule_case_mode(clean_setup: tuple[CleanController, Path]) -> None:
    """case 规则的大小写模式正确解析。."""
    ctrl, _ws = clean_setup
    ctrl.add_rule("case", "name", "", "", "upper")
    rule = ctrl.rulesModel.rule_at(0)
    assert rule is not None
    assert rule.case_mode.value == "upper"
    # 默认模式
    ctrl.add_rule("case", "name", "", "", "")
    rule2 = ctrl.rulesModel.rule_at(1)
    assert rule2 is not None
    assert rule2.case_mode.value == "lower"


def test_preview_without_rules(clean_setup: tuple[CleanController, Path]) -> None:
    """无规则时预览发 error_raised。."""
    ctrl, ws = clean_setup
    signals = _connect_signals(ctrl)
    ctrl.preview(str(ws), "t")
    assert signals == [("error", "请先添加清洗规则")]


def test_preview_populates_model_and_report(clean_setup: tuple[CleanController, Path]) -> None:
    """预览填充模型并生成统计文本。."""
    ctrl, ws = clean_setup
    signals = _connect_signals(ctrl)
    ctrl.add_rule("trim", "name", "", "", "")
    ctrl.preview(str(ws), "t")
    QGuiApplication.processEvents()
    assert ctrl.previewModel.rowCount() == 3
    assert ctrl.previewModel.columnCount() == 2
    # 预览数据已应用 TRIM（首行 name 去除空白）
    idx = ctrl.previewModel.index(0, 0)
    assert ctrl.previewModel.data(idx) == "甲"
    assert "读入行数: 3" in ctrl.reportText  # pyrefly: ignore [not-iterable]
    assert "去除首尾空白" in ctrl.reportText  # pyrefly: ignore [not-iterable]
    assert signals == []


def test_preview_invalid_rule_reports_error(clean_setup: tuple[CleanController, Path]) -> None:
    """规则引用不存在列时预览报错。"""
    ctrl, ws = clean_setup
    signals = _connect_signals(ctrl)
    # 直接操纵底层模型注入非法规则（绕过 add_rule 校验）
    from finaldb.core.cleaning.rules import CleanRule, RuleKind

    ctrl.rulesModel.append_rule(CleanRule(RuleKind.TRIM, "nope"))
    ctrl.preview(str(ws), "t")
    assert signals and signals[0][0] == "error"
    assert "不存在的列" in signals[0][1]


def test_apply_sync_creates_table(clean_setup: tuple[CleanController, Path]) -> None:
    """同步清洗落库并发出 applied 消息。."""
    ctrl, ws = clean_setup
    signals = _connect_signals(ctrl)
    ctrl.add_rule("trim", "name", "", "", "")
    ctrl.add_rule("to_number", "age", "", "", "")
    ctrl.apply_sync(str(ws), "t", "")
    QGuiApplication.processEvents()
    assert signals and signals[0][0] == "applied"
    assert "t_clean" in signals[0][1]
    # 落库校验
    from finaldb.core.storage.database import connect, table_exists

    conn = connect(ws / "data.db")
    try:
        assert table_exists(conn, "t_clean")
        rows = conn.execute('SELECT "name", "age" FROM "t_clean" ORDER BY "age"').fetchall()
        # 无 DROP 规则：3 行全保留，NULL 排序在最前
        assert rows == [("乙", None), (None, 25), ("甲", 30)]
    finally:
        conn.close()


def test_apply_without_rules(clean_setup: tuple[CleanController, Path]) -> None:
    """无规则时应用发 error_raised。."""
    ctrl, ws = clean_setup
    signals = _connect_signals(ctrl)
    ctrl.apply_sync(str(ws), "t", "")
    assert signals == [("error", "请先添加清洗规则")]


def test_apply_sync_failure_emits_failed(clean_setup: tuple[CleanController, Path]) -> None:
    """清洗失败（源表不存在）发 failed 消息。."""
    ctrl, ws = clean_setup
    signals = _connect_signals(ctrl)
    ctrl.add_rule("trim", "name", "", "", "")
    ctrl.apply_sync(str(ws), "missing", "")
    assert signals and signals[0][0] == "failed"
    assert "清洗失败" in signals[0][1]


def test_busy_property_roundtrip(qapp: QGuiApplication) -> None:
    """busy 属性默认 False 且信号触发（内部状态机由线程回调维护）。."""
    ctrl = CleanController()
    assert ctrl.busy is False


def test_apply_async_thread(clean_setup: tuple[CleanController, Path], qapp: QGuiApplication) -> None:
    """异步 apply 在后台线程执行并复位忙状态。."""
    ctrl, ws = clean_setup
    signals = _connect_signals(ctrl)
    ctrl.add_rule("trim", "name", "", "", "")
    ctrl.apply(str(ws), "t", "async_clean")
    assert ctrl.busy is True
    deadline = time.monotonic() + 5.0
    while ctrl.busy and time.monotonic() < deadline:
        qapp.processEvents()
        time.sleep(0.02)
    assert not ctrl.busy
    assert signals and signals[0][0] == "applied"
    assert "async_clean" in signals[0][1]


def test_rule_list_model_roles_and_bounds() -> None:
    """规则模型角色读取与越界防护。."""
    model = CleanRuleListModel()
    model.append_rule(CleanRule(RuleKind.REPLACE, "name", value="-", replacement="_"))
    idx = model.index(0, 0)
    assert model.data(idx, Qt.UserRole + 1) == "replace"
    assert model.data(idx, Qt.UserRole + 2) == "name"
    assert model.data(idx, Qt.UserRole + 3) == "-"
    assert model.data(idx, Qt.UserRole + 4) == "_"
    assert model.data(idx, Qt.UserRole + 5) == "lower"
    assert "替换" in model.data(idx, Qt.UserRole + 6)
    # 未知角色与越界索引返回 None
    assert model.data(idx, Qt.UserRole + 99) is None
    assert model.data(model.index(5, 0), Qt.UserRole + 1) is None
    assert model.data(idx, Qt.DisplayRole) is None
    assert model.rule_at(99) is None
    # remove_row 越界静默
    model.remove_row(99)
    assert model.rowCount() == 1
    model.remove_row(0)
    assert model.rowCount() == 0


def test_string_list_model_roles_and_bounds() -> None:
    """字符串列表模型角色读取与越界防护。."""
    model = StringListModel()
    model.reload(["a", "b"])
    assert model.rowCount() == 2
    assert model.data(model.index(0, 0), Qt.UserRole + 1) == "a"
    assert model.data(model.index(1, 0), Qt.UserRole + 1) == "b"
    # DisplayRole 与越界返回 None
    assert model.data(model.index(0, 0), Qt.DisplayRole) is None
    assert model.data(model.index(9, 0), Qt.UserRole + 1) is None
    assert model.item_at(99) is None
    assert StringListModel().rowCount() == 0
