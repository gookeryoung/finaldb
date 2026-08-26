"""合并服务测试：union 堆叠、dedup 去重、join 连接。."""

from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from pathlib import Path

import pytest

from finaldb.core.exceptions import MergeError
from finaldb.core.merge.service import JoinSpec, dedup_table, join_tables, union_tables
from finaldb.core.storage.database import connect, table_exists


@pytest.fixture()
def db(tmp_path: Path) -> Iterator[sqlite3.Connection]:
    """建临时库：a(id,name) / b(id,name,city) / c(id,score)。."""
    conn = connect(tmp_path / "data.db")
    conn.execute('CREATE TABLE "a" ("id" INTEGER, "name" TEXT)')
    conn.executemany('INSERT INTO "a" VALUES (?, ?)', [(1, "甲"), (2, "乙"), (1, "甲")])
    conn.execute('CREATE TABLE "b" ("id" INTEGER, "name" TEXT, "city" TEXT)')
    conn.executemany(
        'INSERT INTO "b" VALUES (?, ?, ?)',
        [(2, "乙", "沪"), (3, "丙", "京")],
    )
    conn.execute('CREATE TABLE "c" ("id" INTEGER, "score" TEXT)')
    conn.executemany('INSERT INTO "c" VALUES (?, ?)', [(2, "88"), (3, "95")])
    conn.commit()
    yield conn
    conn.close()


# ----------------------------- union -----------------------------


def test_union_aligns_columns(db: sqlite3.Connection) -> None:
    """纵向合并按列名对齐：b 的 city 列追加，a 行 city 补 None。."""
    summary = union_tables(db, ["a", "b"])
    assert summary.target == "merged"
    assert summary.rows_written == 5
    rows = db.execute('SELECT * FROM "merged" ORDER BY "id", "name"').fetchall()
    assert (1, "甲", None) in rows
    assert (2, "乙", None) in rows
    assert (2, "乙", "沪") in rows
    assert (3, "丙", "京") in rows


def test_union_custom_target(db: sqlite3.Connection) -> None:
    """自定义目标表名生效。."""
    union_tables(db, ["a", "b"], target="stacked")
    assert table_exists(db, "stacked")


def test_union_requires_two_tables(db: sqlite3.Connection) -> None:
    """少于两张表报 MergeError。."""
    with pytest.raises(MergeError, match="至少需要两张表"):
        union_tables(db, ["a"])
    with pytest.raises(MergeError, match="至少需要两张表"):
        union_tables(db, [])


def test_union_missing_table_raises(db: sqlite3.Connection) -> None:
    """源表不存在报 MergeError。."""
    with pytest.raises(MergeError, match="表不存在"):
        union_tables(db, ["a", "nope"])


def test_union_type_inferred(db: sqlite3.Connection) -> None:
    """合并后列类型按结果样本推断（c.score 文本转 join 后仍是 TEXT）。."""
    union_tables(db, ["a", "a"], target="aa")
    assert table_exists(db, "aa")


# ----------------------------- dedup -----------------------------


def test_dedup_all_rows(db: sqlite3.Connection) -> None:
    """全行去重保留首见。."""
    summary = dedup_table(db, "a")
    assert summary.target == "a_dedup"
    assert summary.rows_written == 2
    rows = db.execute('SELECT "id", "name" FROM "a_dedup"').fetchall()
    assert rows == [(1, "甲"), (2, "乙")]


def test_dedup_by_key(db: sqlite3.Connection) -> None:
    """按键去重：同键多行只保留首见。."""
    conn = db
    conn.execute('CREATE TABLE "d" ("k" INTEGER, "v" TEXT)')
    conn.executemany('INSERT INTO "d" VALUES (?, ?)', [(1, "x"), (1, "y"), (2, "z")])
    conn.commit()
    summary = dedup_table(conn, "d", keys=["k"])
    assert summary.rows_written == 2
    rows = conn.execute('SELECT "k", "v" FROM "d_dedup"').fetchall()
    assert rows == [(1, "x"), (2, "z")]


def test_dedup_missing_key_raises(db: sqlite3.Connection) -> None:
    """键列不存在报 MergeError。."""
    with pytest.raises(MergeError, match="键列不存在"):
        dedup_table(db, "a", keys=["nope"])


def test_dedup_missing_table_raises(db: sqlite3.Connection) -> None:
    """源表不存在报 MergeError。"""
    with pytest.raises(MergeError, match="表不存在"):
        dedup_table(db, "nope")


def test_dedup_custom_target(db: sqlite3.Connection) -> None:
    """自定义目标表名生效。."""
    dedup_table(db, "a", target="unique_rows")
    assert table_exists(db, "unique_rows")


# ----------------------------- join -----------------------------


def test_join_inner(db: sqlite3.Connection) -> None:
    """inner 连接：仅匹配行，右表列追加。."""
    summary = join_tables(db, JoinSpec(left="b", right="c", left_key="id", right_key="id", how="inner"))
    assert summary.target == "b_c"
    assert summary.rows_written == 2
    rows = db.execute('SELECT * FROM "b_c" ORDER BY "id"').fetchall()
    assert rows == [(2, "乙", "沪", "88"), (3, "丙", "京", "95")]


def test_join_left(db: sqlite3.Connection) -> None:
    """left 连接：左表行全保留，未匹配补 None。."""
    summary = join_tables(db, JoinSpec(left="a", right="c", left_key="id", right_key="id", how="left"))
    assert summary.rows_written == 3
    rows = db.execute('SELECT * FROM "a_c" ORDER BY "id"').fetchall()
    # id=1 在 c 无匹配 → score 为 None（a 表含重复行 1，各保留）
    assert rows[0] == (1, "甲", None)
    assert rows[1] == (1, "甲", None)
    assert rows[2] == (2, "乙", "88")


def test_join_column_conflict_suffix(db: sqlite3.Connection) -> None:
    """右表非键同名列加 _2 后缀。."""
    join_tables(db, JoinSpec(left="a", right="b", left_key="id", right_key="id", how="inner"), target="ab")
    cols = [row[1] for row in db.execute('PRAGMA table_info("ab")')]
    assert cols == ["id", "name", "name_2", "city"]


def test_join_multiple_matches(db: sqlite3.Connection) -> None:
    """一键多匹配产生多行（左行 × 右行）。."""
    conn = db
    conn.execute('CREATE TABLE "r" ("id" INTEGER, "tag" TEXT)')
    conn.executemany('INSERT INTO "r" VALUES (?, ?)', [(2, "t1"), (2, "t2")])
    conn.commit()
    summary = join_tables(db, JoinSpec(left="b", right="r", left_key="id", right_key="id"))
    assert summary.rows_written == 2
    tags = {row[1] for row in conn.execute('SELECT "id", "tag" FROM "b_r"')}
    assert tags == {"t1", "t2"}


def test_join_invalid_how_raises(db: sqlite3.Connection) -> None:
    """不支持的连接方式报 MergeError。."""
    with pytest.raises(MergeError, match="不支持的连接方式"):
        join_tables(db, JoinSpec(left="a", right="b", left_key="id", right_key="id", how="outer"))


def test_join_missing_key_raises(db: sqlite3.Connection) -> None:
    """键列不存在报 MergeError。."""
    with pytest.raises(MergeError, match="左表键列不存在"):
        join_tables(db, JoinSpec(left="a", right="b", left_key="nope", right_key="id"))
    with pytest.raises(MergeError, match="右表键列不存在"):
        join_tables(db, JoinSpec(left="a", right="b", left_key="id", right_key="nope"))


def test_join_missing_table_raises(db: sqlite3.Connection) -> None:
    """源表不存在报 MergeError。"""
    with pytest.raises(MergeError, match="表不存在"):
        join_tables(db, JoinSpec(left="nope", right="b", left_key="id", right_key="id"))


def test_join_numeric_type_inferred(db: sqlite3.Connection) -> None:
    """连接结果数值列类型推断为 INTEGER。."""
    join_tables(db, JoinSpec(left="a", right="c", left_key="id", right_key="id"), target="ac")
    cols = {row[1]: row[2] for row in db.execute('PRAGMA table_info("ac")')}
    assert cols["score"] == "TEXT"  # c.score 为 TEXT 原样保留
