"""历史控制器测试：快照列表加载、提交/回滚/对比同步与异步路径。."""

from __future__ import annotations

import sqlite3
import time
from pathlib import Path

import pytest
from PySide2.QtGui import QGuiApplication

from finaldb.core.versioning import SnapshotInfo, commit_snapshot
from finaldb.gui.controllers.history_controller import HistoryController

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
def history_setup(qapp: QGuiApplication, tmp_path: Path) -> tuple[HistoryController, Path, SnapshotInfo, SnapshotInfo]:
    """构造带两个快照的临时工作区与控制器。."""
    from finaldb.core.storage.database import connect

    ws = tmp_path / "ws"
    ws.mkdir()
    conn = connect(ws / "data.db")
    conn.execute('CREATE TABLE "t" ("name" TEXT)')
    conn.executemany('INSERT INTO "t" VALUES (?)', [("甲",), ("乙",)])
    conn.commit()
    conn.close()
    first = commit_snapshot(ws, "初始导入")

    conn = connect(ws / "data.db")
    conn.execute('INSERT INTO "t" VALUES (?)', ("丙",))
    conn.commit()
    conn.close()
    second = commit_snapshot(ws, "新增丙")

    ctrl = HistoryController()
    return ctrl, ws, first, second


def _connect_signals(ctrl: HistoryController) -> list[tuple[str, str]]:
    """挂接错误/完成信号到收集器并清空旧记录。."""
    _SIGNALS.clear()
    ctrl.error_raised.connect(_on_error)  # pyrefly: ignore [missing-attribute]
    ctrl.applied.connect(_on_applied)  # pyrefly: ignore [missing-attribute]
    ctrl.failed.connect(_on_failed)  # pyrefly: ignore [missing-attribute]
    return _SIGNALS


def _rows_of(ws: Path, table: str) -> list[tuple[object, ...]]:
    """读取指定表全部行（按首列排序稳定断言）。."""
    from finaldb.core.storage.database import connect

    conn = connect(ws / "data.db")
    try:
        return conn.execute(f'SELECT * FROM "{table}" ORDER BY 1').fetchall()
    finally:
        conn.close()


def test_load_history(history_setup: tuple[HistoryController, Path, SnapshotInfo, SnapshotInfo]) -> None:
    """load_history 按时间倒序加载快照列表。."""
    ctrl, ws, _first, second = history_setup
    ctrl.load_history(str(ws))
    assert ctrl.snapshots_model().rowCount() == 2
    top = ctrl.snapshots_model().snapshot_at(0)
    assert top is not None and top.short_id == second.short_id


def test_load_history_empty_path(history_setup: tuple[HistoryController, Path, SnapshotInfo, SnapshotInfo]) -> None:
    """空路径清空快照列表。"""
    ctrl, ws, _first, _second = history_setup
    ctrl.load_history(str(ws))
    ctrl.load_history("")
    assert ctrl.snapshots_model().rowCount() == 0


def test_commit_sync(
    history_setup: tuple[HistoryController, Path, SnapshotInfo, SnapshotInfo], qapp: QGuiApplication
) -> None:
    """同步提交新快照：发 applied 并进入列表。"""
    ctrl, ws, _first, _second = history_setup
    signals = _connect_signals(ctrl)
    conn = _open(ws)
    conn.execute('INSERT INTO "t" VALUES (?)', ("丁",))
    conn.commit()
    conn.close()
    ctrl.commit_sync(str(ws), "新增丁")
    qapp.processEvents()
    assert signals and signals[0][0] == "applied"
    assert "已提交快照" in signals[0][1]
    ctrl.load_history(str(ws))
    assert ctrl.snapshots_model().rowCount() == 3


def _open(ws: Path) -> sqlite3.Connection:
    """连接工作区数据库（内部辅助）。."""
    from finaldb.core.storage.database import connect

    return connect(ws / "data.db")


def test_commit_no_changes_failed(
    history_setup: tuple[HistoryController, Path, SnapshotInfo, SnapshotInfo], qapp: QGuiApplication
) -> None:
    """无变化提交发 failed 消息。"""
    ctrl, ws, _first, _second = history_setup
    signals = _connect_signals(ctrl)
    ctrl.commit_sync(str(ws), "空提交")
    qapp.processEvents()
    assert signals and signals[0][0] == "failed"
    assert "版本操作失败" in signals[0][1]


def test_restore_sync(
    history_setup: tuple[HistoryController, Path, SnapshotInfo, SnapshotInfo], qapp: QGuiApplication
) -> None:
    """同步回滚到首个快照：数据恢复两行。"""
    ctrl, ws, first, _second = history_setup
    signals = _connect_signals(ctrl)
    ctrl.restore_sync(str(ws), first.short_id)
    qapp.processEvents()
    assert signals and signals[0][0] == "applied"
    assert "已回滚到快照" in signals[0][1]
    rows = _rows_of(ws, "t")
    assert len(rows) == 2
    assert set(rows) == {("甲",), ("乙",)}


def test_diff_sync(
    history_setup: tuple[HistoryController, Path, SnapshotInfo, SnapshotInfo], qapp: QGuiApplication
) -> None:
    """同步对比两个快照：diffText 更新并含表级行数。"""
    ctrl, ws, first, second = history_setup
    signals = _connect_signals(ctrl)
    assert ctrl.diff_text() == ""
    ctrl.diff_sync(str(ws), first.short_id, second.short_id)
    qapp.processEvents()
    assert signals and signals[0][0] == "applied"
    assert "表 t" in ctrl.diff_text()
    assert "3 行" in ctrl.diff_text()


def test_restore_empty_ref_error(
    history_setup: tuple[HistoryController, Path, SnapshotInfo, SnapshotInfo], qapp: QGuiApplication
) -> None:
    """回滚未选快照发 error_raised。"""
    ctrl, ws, _first, _second = history_setup
    signals = _connect_signals(ctrl)
    ctrl.restore(str(ws), "")
    qapp.processEvents()
    assert signals and signals[0][0] == "error"
    assert "请先选择" in signals[0][1]


def test_diff_empty_ref_error(
    history_setup: tuple[HistoryController, Path, SnapshotInfo, SnapshotInfo], qapp: QGuiApplication
) -> None:
    """对比未选齐两快照发 error_raised。"""
    ctrl, ws, first, _second = history_setup
    signals = _connect_signals(ctrl)
    ctrl.diff(str(ws), first.short_id, "")
    qapp.processEvents()
    assert signals and signals[0][0] == "error"
    assert "请先选择" in signals[0][1]


def test_busy_property_default(qapp: QGuiApplication) -> None:
    """busy 属性默认 False。."""
    ctrl = HistoryController()
    assert ctrl.is_busy() is False


def test_commit_async_thread(
    history_setup: tuple[HistoryController, Path, SnapshotInfo, SnapshotInfo], qapp: QGuiApplication
) -> None:
    """异步提交在后台线程执行并复位忙状态。"""
    ctrl, ws, _first, _second = history_setup
    signals = _connect_signals(ctrl)
    conn = _open(ws)
    conn.execute('INSERT INTO "t" VALUES (?)', ("戊",))
    conn.commit()
    conn.close()
    ctrl.commit(str(ws), "异步新增戊")
    assert ctrl.is_busy() is True
    deadline = time.monotonic() + 5.0
    while ctrl.is_busy() and time.monotonic() < deadline:
        qapp.processEvents()
        time.sleep(0.02)
    assert not ctrl.is_busy()
    assert signals and signals[0][0] == "applied"
    assert "异步新增戊" in signals[0][1]
