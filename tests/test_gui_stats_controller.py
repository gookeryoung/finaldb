"""统计控制器测试：摘要文本、表分布加载与边界路径。."""

from __future__ import annotations

from pathlib import Path

import pytest

from finaldb.gui.controllers.stats_controller import StatsController

pytestmark = pytest.mark.gui


@pytest.fixture()
def stats_setup(qapp: object, tmp_path: Path) -> tuple[StatsController, Path]:
    """构造带两张数据表的临时工作区与控制器。."""
    from finaldb.core.storage.database import connect

    ws = tmp_path / "ws"
    ws.mkdir()
    conn = connect(ws / "data.db")
    conn.execute('CREATE TABLE "t1" ("name" TEXT)')
    conn.executemany('INSERT INTO "t1" VALUES (?)', [("甲",), ("乙",), ("丙",)])
    conn.execute('CREATE TABLE "t2" ("city" TEXT, "pop" INTEGER)')
    conn.execute('INSERT INTO "t2" VALUES (?, ?)', ("北京", 100))
    conn.commit()
    conn.close()
    return StatsController(), ws


def test_load_stats(stats_setup: tuple[StatsController, Path]) -> None:
    """load_stats 加载表分布与摘要。."""
    ctrl, ws = stats_setup
    ctrl.load_stats(str(ws))
    model = ctrl.statsModel
    assert model.rowCount() == 2
    first = model.stat_at(0)
    assert first is not None and first.name == "t1"
    assert first.row_count == 3
    assert ctrl.summaryText == "共 2 张表，4 行数据"


def test_load_stats_ratio_role(stats_setup: tuple[StatsController, Path]) -> None:
    """ratio 角色按最大行数归一化。"""
    from PySide2.QtCore import Qt

    ctrl, ws = stats_setup
    ctrl.load_stats(str(ws))
    model = ctrl.statsModel
    assert model.max_rows() == 3
    ratio_t1 = model.data(model.index(0, 0), Qt.UserRole + 5)
    ratio_t2 = model.data(model.index(1, 0), Qt.UserRole + 5)
    assert ratio_t1 == pytest.approx(1.0)
    assert ratio_t2 == pytest.approx(1 / 3)


def test_load_stats_empty_path(stats_setup: tuple[StatsController, Path]) -> None:
    """空路径清空模型并提示未选工作区。."""
    ctrl, _ws = stats_setup
    ctrl.load_stats("")
    assert ctrl.statsModel.rowCount() == 0
    assert "未选择工作区" in str(ctrl.summaryText)


def test_load_stats_no_db(stats_setup: tuple[StatsController, Path], tmp_path: Path) -> None:
    """工作区无数据库文件时提示暂无数据。."""
    ctrl, _ws = stats_setup
    empty = tmp_path / "empty"
    empty.mkdir()
    ctrl.load_stats(str(empty))
    assert ctrl.statsModel.rowCount() == 0
    assert "暂无数据" in str(ctrl.summaryText)


def test_stat_at_out_of_range(stats_setup: tuple[StatsController, Path]) -> None:
    """stat_at 越界返回 None。."""
    ctrl, ws = stats_setup
    ctrl.load_stats(str(ws))
    assert ctrl.statsModel.stat_at(5) is None
    assert ctrl.statsModel.stat_at(-1) is None


def test_display_role(stats_setup: tuple[StatsController, Path]) -> None:
    """display 角色为单行摘要。."""
    from PySide2.QtCore import Qt

    ctrl, ws = stats_setup
    ctrl.load_stats(str(ws))
    display = ctrl.statsModel.data(ctrl.statsModel.index(0, 0), Qt.UserRole + 4)
    assert display == "t1（1 列 / 3 行）"
