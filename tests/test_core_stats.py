"""core 统计分析单测：工作区概览、列级统计与体积格式化。."""

from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from pathlib import Path

import pytest

from finaldb.core.stats import (
    ColumnStat,
    TopNullColumn,
    WorkspaceOverview,
    column_stats,
    format_size,
    top_null_columns,
    type_distribution,
    workspace_overview,
)


@pytest.fixture()
def db(tmp_path: Path) -> Iterator[tuple[sqlite3.Connection, Path]]:
    """构造带一张混合类型表（含空值/重复值）的临时数据库。."""
    path = tmp_path / "data.db"
    conn = sqlite3.connect(str(path))
    conn.execute('CREATE TABLE "t" ("name" TEXT, "age" INTEGER)')
    conn.executemany(
        'INSERT INTO "t" VALUES (?, ?)',
        [("甲", 30), ("甲", 25), (None, None), ("乙", 40)],
    )
    conn.commit()
    yield conn, path
    conn.close()


def test_workspace_overview(db: tuple[sqlite3.Connection, Path]) -> None:
    """概览统计：表数/行数/列数/体积。."""
    conn, path = db
    overview = workspace_overview(conn, path)
    assert overview == WorkspaceOverview(table_count=1, total_rows=4, total_columns=2, db_bytes=path.stat().st_size)


def test_workspace_overview_missing_file(tmp_path: Path) -> None:
    """库文件不存在时体积为 0。."""
    conn = sqlite3.connect(":memory:")
    conn.execute('CREATE TABLE "t" ("x" INTEGER)')
    overview = workspace_overview(conn, tmp_path / "ghost.db")
    assert overview.db_bytes == 0
    assert overview.table_count == 1
    conn.close()


def test_column_stats(db: tuple[sqlite3.Connection, Path]) -> None:
    """列级统计：空值/唯一值/最值/均值画像。."""
    conn, _path = db
    stats = column_stats(conn, "t")
    assert len(stats) == 2

    name_stat, age_stat = stats
    assert name_stat.name == "name"
    assert name_stat.sql_type == "TEXT"
    assert name_stat.total == 4
    assert name_stat.non_null == 3
    assert name_stat.null_count == 1
    assert name_stat.distinct_count == 2  # 甲/乙（重复甲只计一次，NULL 不计）
    # SQLite 文本比较按码点：乙(U+4E59) < 甲(U+7532)
    assert name_stat.minimum == "乙"
    assert name_stat.maximum == "甲"
    assert name_stat.mean is None  # TEXT 列不计算均值

    assert age_stat.name == "age"
    assert age_stat.sql_type == "INTEGER"
    assert age_stat.null_count == 1
    assert age_stat.minimum == 25
    assert age_stat.maximum == 40
    assert age_stat.mean == pytest.approx(31.6667)


def test_column_stats_missing_table(db: tuple[sqlite3.Connection, Path]) -> None:
    """表不存在返回空列表。."""
    conn, _path = db
    assert column_stats(conn, "ghost") == []


def test_column_stat_is_frozen(db: tuple[sqlite3.Connection, Path]) -> None:
    """ColumnStat 为 frozen dataclass（统计快照不可变）。."""
    conn, _path = db
    stat = column_stats(conn, "t")[0]
    assert isinstance(stat, ColumnStat)
    with pytest.raises(AttributeError):
        stat.null_count = 99  # type: ignore[misc]


def test_format_size() -> None:
    """体积格式化：B/KB/MB/GB/TB 分级与保留一位小数。."""
    assert format_size(0) == "0 B"
    assert format_size(512) == "512 B"
    assert format_size(1024) == "1.0 KB"
    assert format_size(1536) == "1.5 KB"
    assert format_size(1024 * 1024) == "1.0 MB"
    assert format_size(1024**3) == "1.0 GB"
    assert format_size(1024**4) == "1.0 TB"


def test_type_distribution(db: tuple[sqlite3.Connection, Path]) -> None:
    """类型分布：按列数降序排列。."""
    conn, _path = db
    conn.execute('CREATE TABLE "u" ("a" TEXT, "b" TEXT, "c" INTEGER)')
    conn.commit()
    assert type_distribution(conn) == [("TEXT", 3), ("INTEGER", 2)]


def test_top_null_columns(db: tuple[sqlite3.Connection, Path]) -> None:
    """空值 TOP：按空值数降序取前 N，无空值列不进入榜单。."""
    conn, _path = db
    conn.execute('CREATE TABLE "u" ("x" TEXT, "y" TEXT)')
    conn.executemany('INSERT INTO "u" VALUES (?, ?)', [(None, "a"), (None, None), ("z", "b")])
    conn.commit()
    result = top_null_columns(conn)
    # u.x 2 个空值 > t.name/t.age/u.y 各 1 个
    assert result[0] == TopNullColumn(table="u", column="x", null_count=2, total=3)
    assert all(item.null_count == 1 for item in result[1:])
    assert len(result) == 4  # t.name/t.age/u.x/u.y
    assert top_null_columns(conn, limit=2) == result[:2]
