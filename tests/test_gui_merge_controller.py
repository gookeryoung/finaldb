"""合并控制器测试：表/列加载、union/dedup/join 同步与异步落库。."""

from __future__ import annotations

import time
from pathlib import Path

import pytest
from PySide2.QtGui import QGuiApplication

from finaldb.gui.controllers.merge_controller import MergeController

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
def merge_setup(qapp: QGuiApplication, tmp_path: Path) -> tuple[MergeController, Path]:
    """构造带两张数据表的临时工作区与控制器。."""
    from finaldb.core.storage.database import connect

    ws = tmp_path / "ws"
    ws.mkdir()
    conn = connect(ws / "data.db")
    conn.execute('CREATE TABLE "t1" ("name" TEXT, "age" INTEGER)')
    conn.executemany(
        'INSERT INTO "t1" VALUES (?, ?)',
        [("甲", 30), ("乙", 25), ("乙", 25)],
    )
    conn.execute('CREATE TABLE "t2" ("name" TEXT, "city" TEXT)')
    conn.executemany(
        'INSERT INTO "t2" VALUES (?, ?)',
        [("甲", "北京"), ("丙", "上海"), ("丁", "广州"), ("甲", "深圳")],
    )
    conn.commit()
    conn.close()

    ctrl = MergeController()
    ctrl.load_tables(str(ws))
    return ctrl, ws


def _connect_signals(ctrl: MergeController) -> list[tuple[str, str]]:
    """挂接错误/完成信号到收集器并清空旧记录。."""
    _SIGNALS.clear()
    ctrl.error_raised.connect(_on_error)  # pyrefly: ignore [missing-attribute]
    ctrl.applied.connect(_on_applied)  # pyrefly: ignore [missing-attribute]
    ctrl.failed.connect(_on_failed)  # pyrefly: ignore [missing-attribute]
    return _SIGNALS


def _rows_of(ws: Path, table: str) -> list[tuple[object, ...]]:
    """读取指定表全部行（按首列排序稳定断言）。."""
    from finaldb.core.storage.database import connect, table_exists

    conn = connect(ws / "data.db")
    try:
        if not table_exists(conn, table):
            return []
        return conn.execute(f'SELECT * FROM "{table}"').fetchall()
    finally:
        conn.close()


def test_load_tables(merge_setup: tuple[MergeController, Path]) -> None:
    """load_tables 加载表列表。."""
    ctrl, _ws = merge_setup
    assert ctrl.tables_model().rowCount() == 2
    assert ctrl.tables_model().table_at(0) == "t1"
    assert ctrl.tables_model().table_at(1) == "t2"


def test_load_tables_empty_path(merge_setup: tuple[MergeController, Path]) -> None:
    """空路径清空表列表。"""
    ctrl, _ws = merge_setup
    ctrl.load_tables("")
    assert ctrl.tables_model().rowCount() == 0


def test_load_columns(merge_setup: tuple[MergeController, Path]) -> None:
    """load_columns 加载去重键候选列。."""
    ctrl, ws = merge_setup
    ctrl.load_columns(str(ws), "t1")
    assert ctrl.dedup_columns_model().rowCount() == 2
    assert ctrl.dedup_columns_model().item_at(0) == "name"
    # 空参数清空
    ctrl.load_columns("", "")
    assert ctrl.dedup_columns_model().rowCount() == 0


def test_load_join_columns(merge_setup: tuple[MergeController, Path]) -> None:
    """load_join_columns 分别加载左右表列。."""
    ctrl, ws = merge_setup
    ctrl.load_join_columns(str(ws), "t1", "t2")
    assert ctrl.left_columns_model().item_at(0) == "name"
    assert ctrl.left_columns_model().item_at(1) == "age"
    assert ctrl.right_columns_model().item_at(0) == "name"
    assert ctrl.right_columns_model().item_at(1) == "city"
    # 空右表清空右模型
    ctrl.load_join_columns(str(ws), "t1", "")
    assert ctrl.right_columns_model().rowCount() == 0


def test_apply_union_sync(merge_setup: tuple[MergeController, Path], qapp: QGuiApplication) -> None:
    """同步纵向合并：列对齐（t2 的 city 追加，t1 的 age 补空）。."""
    ctrl, ws = merge_setup
    signals = _connect_signals(ctrl)
    ctrl.apply_union_sync(str(ws), "t1\x1ft2", "")
    qapp.processEvents()
    assert signals and signals[0][0] == "applied"
    rows = _rows_of(ws, "merged")
    assert len(rows) == 7
    assert {row[2] for row in rows} == {None, "北京", "上海", "广州", "深圳"}
    assert signals[0][1].startswith("已合并 t1、t2")


def test_apply_dedup_sync(merge_setup: tuple[MergeController, Path], qapp: QGuiApplication) -> None:
    """同步全行去重：重复行（乙,25）只保留一次。."""
    ctrl, ws = merge_setup
    signals = _connect_signals(ctrl)
    ctrl.apply_dedup_sync(str(ws), "t1", "", "")
    qapp.processEvents()
    assert signals and signals[0][0] == "applied"
    assert len(_rows_of(ws, "t1_dedup")) == 2


def test_apply_dedup_sync_by_key(merge_setup: tuple[MergeController, Path], qapp: QGuiApplication) -> None:
    """按键列去重：右表 t2 按 name 去重后甲保留首见（北京）。."""
    ctrl, ws = merge_setup
    signals = _connect_signals(ctrl)
    ctrl.apply_dedup_sync(str(ws), "t2", "name", "u2")
    qapp.processEvents()
    assert signals and signals[0][0] == "applied"
    rows = _rows_of(ws, "u2")
    assert len(rows) == 3
    assert ("甲", "北京") in rows


def _join_params(left: str, right: str, how: str, target: str = "") -> str:
    """构造 apply_join 的 6 段拼接参数。."""
    return "\x1f".join((left, right, "name", "name", how, target))


def test_apply_join_sync_inner(merge_setup: tuple[MergeController, Path], qapp: QGuiApplication) -> None:
    """同步内连接：仅保留匹配行，甲一键两匹配展开两行。."""
    ctrl, ws = merge_setup
    signals = _connect_signals(ctrl)
    ctrl.apply_join_sync(str(ws), _join_params("t1", "t2", "inner", "j"))
    qapp.processEvents()
    assert signals and signals[0][0] == "applied"
    # 结果列序 = 左表列（name, age）+ 右表非键列（city）；甲一键两匹配展开两行
    rows = _rows_of(ws, "j")
    assert sorted(rows) == [("甲", 30, "北京"), ("甲", 30, "深圳")]
    assert "匹配 2 行" in signals[0][1]


def test_apply_join_sync_left(merge_setup: tuple[MergeController, Path], qapp: QGuiApplication) -> None:
    """同步左连接：左表全保留，未匹配右字段补空。"""
    ctrl, ws = merge_setup
    signals = _connect_signals(ctrl)
    ctrl.apply_join_sync(str(ws), _join_params("t1", "t2", "left", "lj"))
    qapp.processEvents()
    assert signals and signals[0][0] == "applied"
    rows = _rows_of(ws, "lj")
    # t1 去重前 3 行：乙两行无匹配补空，甲一行两匹配
    assert len(rows) == 4
    assert ("乙", 25, None) in rows


def test_apply_failure_emits_failed(merge_setup: tuple[MergeController, Path], qapp: QGuiApplication) -> None:
    """合并失败（表不存在）发 failed 消息。"""
    ctrl, ws = merge_setup
    signals = _connect_signals(ctrl)
    ctrl.apply_dedup_sync(str(ws), "missing", "", "")
    qapp.processEvents()
    assert signals and signals[0][0] == "failed"
    assert "合并失败" in signals[0][1]


def test_busy_property_default(qapp: QGuiApplication) -> None:
    """busy 属性默认 False。."""
    ctrl = MergeController()
    assert ctrl.is_busy() is False


def test_apply_union_async_thread(merge_setup: tuple[MergeController, Path], qapp: QGuiApplication) -> None:
    """异步 union 在后台线程执行并复位忙状态。"""
    ctrl, ws = merge_setup
    signals = _connect_signals(ctrl)
    ctrl.apply_union(str(ws), "t1\x1ft2", "async_merged")
    assert ctrl.is_busy() is True
    deadline = time.monotonic() + 5.0
    while ctrl.is_busy() and time.monotonic() < deadline:
        qapp.processEvents()
        time.sleep(0.02)
    assert not ctrl.is_busy()
    assert signals and signals[0][0] == "applied"
    assert "async_merged" in signals[0][1]
    assert len(_rows_of(ws, "async_merged")) == 7
