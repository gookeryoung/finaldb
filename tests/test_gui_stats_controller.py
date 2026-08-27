"""统计控制器测试：摘要文本、表分布加载、列级统计与边界路径。."""

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
    """load_stats 加载表分布与摘要（表数/行数/列数/体积）。."""
    ctrl, ws = stats_setup
    ctrl.load_stats(str(ws))
    model = ctrl.stats_model()
    assert model.rowCount() == 2
    first = model.stat_at(0)
    assert first is not None and first.name == "t1"
    assert first.row_count == 3
    summary = ctrl.summary_text()
    assert summary.startswith("共 2 张表 · 4 行 · 3 列 · ")


def test_load_stats_ratio_role(stats_setup: tuple[StatsController, Path]) -> None:
    """ratio 角色按最大行数归一化。"""
    from PySide2.QtCore import Qt

    ctrl, ws = stats_setup
    ctrl.load_stats(str(ws))
    model = ctrl.stats_model()
    assert model.max_rows() == 3
    ratio_t1 = model.data(model.index(0, 0), Qt.UserRole + 5)
    ratio_t2 = model.data(model.index(1, 0), Qt.UserRole + 5)
    assert ratio_t1 == pytest.approx(1.0)
    assert ratio_t2 == pytest.approx(1 / 3)


def test_load_stats_empty_path(stats_setup: tuple[StatsController, Path]) -> None:
    """空路径清空模型并提示未选工作区。."""
    ctrl, _ws = stats_setup
    ctrl.load_stats("")
    assert ctrl.stats_model().rowCount() == 0
    assert "未选择工作区" in str(ctrl.summary_text())


def test_load_stats_no_db(stats_setup: tuple[StatsController, Path], tmp_path: Path) -> None:
    """工作区无数据库文件时提示暂无数据。."""
    ctrl, _ws = stats_setup
    empty = tmp_path / "empty"
    empty.mkdir()
    ctrl.load_stats(str(empty))
    assert ctrl.stats_model().rowCount() == 0
    assert "暂无数据" in str(ctrl.summary_text())


def test_stat_at_out_of_range(stats_setup: tuple[StatsController, Path]) -> None:
    """stat_at 越界返回 None。."""
    ctrl, ws = stats_setup
    ctrl.load_stats(str(ws))
    assert ctrl.stats_model().stat_at(5) is None
    assert ctrl.stats_model().stat_at(-1) is None


def test_display_role(stats_setup: tuple[StatsController, Path]) -> None:
    """display 角色为单行摘要。."""
    from PySide2.QtCore import Qt

    ctrl, ws = stats_setup
    ctrl.load_stats(str(ws))
    display = ctrl.stats_model().data(ctrl.stats_model().index(0, 0), Qt.UserRole + 4)
    assert display == "t1（1 列 / 3 行）"


def test_table_names(stats_setup: tuple[StatsController, Path]) -> None:
    """table_names 返回当前工作区全部表名。."""
    ctrl, ws = stats_setup
    ctrl.load_stats(str(ws))
    assert ctrl.table_names() == ["t1", "t2"]
    ctrl.load_stats("")
    assert ctrl.table_names() == []


def test_load_table_stats(stats_setup: tuple[StatsController, Path]) -> None:
    """load_table_stats 加载单表列级统计画像。."""
    ctrl, ws = stats_setup
    ctrl.load_table_stats(str(ws), "t2")
    model = ctrl.table_stats_model()
    assert model.rowCount() == 2
    city_stat = model.stat_at(0)
    pop_stat = model.stat_at(1)
    assert city_stat is not None and city_stat.name == "city"
    assert city_stat.sql_type == "TEXT"
    assert city_stat.total == 1 and city_stat.non_null == 1 and city_stat.null_count == 0
    assert city_stat.distinct_count == 1
    assert city_stat.minimum == "北京" and city_stat.maximum == "北京"
    assert city_stat.mean is None  # TEXT 列不计算均值
    assert pop_stat is not None and pop_stat.name == "pop"
    assert pop_stat.mean == 100.0


def test_load_table_stats_empty_inputs(stats_setup: tuple[StatsController, Path]) -> None:
    """未选工作区/表名或表不存在时列统计清空。."""
    ctrl, ws = stats_setup
    ctrl.load_table_stats(str(ws), "t2")
    assert ctrl.table_stats_model().rowCount() == 2
    ctrl.load_table_stats("", "t2")
    assert ctrl.table_stats_model().rowCount() == 0
    ctrl.load_table_stats(str(ws), "t2")
    ctrl.load_table_stats(str(ws), "")
    assert ctrl.table_stats_model().rowCount() == 0
    # 表不存在返回空列表
    ctrl.load_table_stats(str(ws), "ghost")
    assert ctrl.table_stats_model().rowCount() == 0


def test_column_stat_model_display(stats_setup: tuple[StatsController, Path]) -> None:
    """ColumnStatModel 二维表数据与表头（None 显示空串）。."""
    from PySide2.QtCore import Qt

    ctrl, ws = stats_setup
    ctrl.load_table_stats(str(ws), "t1")
    model = ctrl.table_stats_model()
    assert model.columnCount() == 8
    # 全非空：空值列显示 0，均值显示空串（TEXT 列）
    idx = model.index(0, 0)
    assert model.data(idx, Qt.DisplayRole) == "name"
    assert model.data(model.index(0, 3), Qt.DisplayRole) == "0"
    assert model.data(model.index(0, 7), Qt.DisplayRole) == ""
    # 表头
    assert model.headerData(0, Qt.Horizontal, Qt.DisplayRole) == "列名"
    assert model.headerData(7, Qt.Horizontal, Qt.DisplayRole) == "平均值"
    # 非 DisplayRole / 越界行返回 None
    assert model.data(idx, Qt.EditRole) is None
    assert model.data(model.index(9, 0), Qt.DisplayRole) is None
    assert model.stat_at(9) is None
