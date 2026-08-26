"""清洗服务测试：clean_table 落库、类型推断、目标表名。."""

from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from pathlib import Path

import pytest

from finaldb.core.cleaning.rules import CleanRule, RuleKind
from finaldb.core.cleaning.service import clean_table
from finaldb.core.exceptions import CleanError
from finaldb.core.storage.database import column_infos, connect, table_exists


@pytest.fixture()
def db(tmp_path: Path) -> Iterator[sqlite3.Connection]:
    """建临时库并写入源表 t（含脏数据）。."""
    conn = connect(tmp_path / "data.db")
    conn.execute('CREATE TABLE "t" ("name" TEXT, "age" TEXT)')
    conn.executemany(
        'INSERT INTO "t" VALUES (?, ?)',
        [(" 甲 ", "30"), ("乙", None), (None, "25")],
    )
    conn.commit()
    yield conn
    conn.close()


def test_clean_table_creates_new_table(db: sqlite3.Connection) -> None:
    """清洗生成新表：TRIM + TO_NUMBER + DROP_MISSING 组合。."""
    rules = [
        CleanRule(RuleKind.TRIM, "name"),
        CleanRule(RuleKind.TO_NUMBER, "age"),
        CleanRule(RuleKind.DROP_MISSING, "age"),
    ]
    summary = clean_table(db, "t", rules)
    assert summary.source == "t"
    assert summary.target == "t_clean"
    assert summary.rows_written == 2
    rows = db.execute('SELECT "name", "age" FROM "t_clean" ORDER BY "age"').fetchall()
    assert rows == [(None, 25), ("甲", 30)]
    # 源表原样保留
    assert table_exists(db, "t")
    assert db.execute('SELECT COUNT(*) FROM "t"').fetchone()[0] == 3


def test_clean_table_column_type_inferred(db: sqlite3.Connection) -> None:
    """TO_NUMBER 后新表列类型推断为 INTEGER。."""
    summary = clean_table(db, "t", [CleanRule(RuleKind.TO_NUMBER, "age")])
    cols = {c.name: c.sql_type for c in column_infos(db, summary.target)}
    assert cols["age"] == "INTEGER"
    assert cols["name"] == "TEXT"


def test_clean_table_auto_target_suffix(db: sqlite3.Connection) -> None:
    """目标表名冲突时自动追加序号。."""
    clean_table(db, "t", [CleanRule(RuleKind.TRIM, "name")])
    second = clean_table(db, "t", [CleanRule(RuleKind.TRIM, "name")])
    assert second.target == "t_clean_2"


def test_clean_table_custom_target(db: sqlite3.Connection) -> None:
    """自定义目标表名生效。."""
    summary = clean_table(db, "t", [CleanRule(RuleKind.TRIM, "name")], target="washed")
    assert summary.target == "washed"
    assert table_exists(db, "washed")


def test_clean_table_missing_source_raises(db: sqlite3.Connection) -> None:
    """源表不存在报 CleanError。."""
    with pytest.raises(CleanError, match="表不存在"):
        clean_table(db, "nope", [CleanRule(RuleKind.TRIM, "name")])


def test_clean_table_invalid_rules_raises(db: sqlite3.Connection) -> None:
    """规则引用不存在的列报 CleanError，且不产生新表。."""
    with pytest.raises(CleanError, match="不存在的列"):
        clean_table(db, "t", [CleanRule(RuleKind.TRIM, "nope")])
    assert not table_exists(db, "t_clean")


def test_clean_table_empty_source(db: sqlite3.Connection) -> None:
    """空源表清洗产出空新表（列全 TEXT）。."""
    db.execute('CREATE TABLE "empty" ("a" TEXT)')
    db.commit()
    summary = clean_table(db, "empty", [CleanRule(RuleKind.TRIM, "a")])
    assert summary.rows_written == 0
    assert table_exists(db, "empty_clean")
    cols = column_infos(db, "empty_clean")
    assert [c.name for c in cols] == ["a"]


def test_clean_summary_report(db: sqlite3.Connection) -> None:
    """摘要携带完整报告统计。."""
    summary = clean_table(db, "t", [CleanRule(RuleKind.TRIM, "name")])
    assert summary.report.total_rows == 3
    assert summary.report.changed_cells == [1]


def test_clean_table_fill_missing_numeric(db: sqlite3.Connection) -> None:
    """TO_NUMBER 后缺失填充数值，新表列类型为 INTEGER。."""
    rules = [
        CleanRule(RuleKind.TO_NUMBER, "age"),
        CleanRule(RuleKind.FILL_MISSING, "age", value="0"),
    ]
    summary = clean_table(db, "t", rules)
    assert summary.rows_written == 3
    rows = db.execute('SELECT "age" FROM "t_clean" ORDER BY "age"').fetchall()
    assert rows == [(0,), (25,), (30,)]
    cols = {c.name: c.sql_type for c in column_infos(db, summary.target)}
    assert cols["age"] == "INTEGER"
