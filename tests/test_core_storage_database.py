"""SQLite 存储层测试：建表/插入/元数据/标识符校验。."""

from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from pathlib import Path

import pytest

from finaldb.core.exceptions import TableExistsError
from finaldb.core.storage.database import (
    column_infos,
    connect,
    create_table,
    drop_table,
    fetch_preview,
    find_free_table_name,
    infer_sql_type,
    insert_rows,
    quote_identifier,
    table_exists,
    table_infos,
    table_names,
    validate_identifier,
)


@pytest.fixture()
def conn(tmp_path: Path) -> Iterator[sqlite3.Connection]:
    """临时数据库连接。."""
    connection = connect(tmp_path / "test.db")
    yield connection
    connection.close()


def test_connect_creates_db_file(tmp_path: Path) -> None:
    """connect 应隐式创建数据库文件。."""
    db = tmp_path / "new.db"
    c = connect(db)
    c.close()
    assert db.is_file()


def test_validate_identifier_rules() -> None:
    """标识符黑名单校验：引号/空白/控制字符非法，中文合法。."""
    assert validate_identifier("valid_name_1") == "valid_name_1"
    assert validate_identifier("a") == "a"
    assert validate_identifier("中文表") == "中文表"
    with pytest.raises(ValueError, match="非法标识符"):
        validate_identifier('bad"name')
    with pytest.raises(ValueError, match="非法标识符"):
        validate_identifier("drop table;--")
    with pytest.raises(ValueError, match="非法标识符"):
        validate_identifier("line\nbreak")
    with pytest.raises(ValueError, match="非法标识符"):
        validate_identifier("")


def test_quote_identifier_wraps() -> None:
    """合法标识符应被双引号包裹。."""
    assert quote_identifier("t") == '"t"'


def test_infer_sql_type_matrix() -> None:
    """类型推断：全 int→INTEGER，混合 float→REAL，其余 TEXT。."""
    assert infer_sql_type([1, 2, 3]) == "INTEGER"
    assert infer_sql_type([1, 2.5]) == "REAL"
    assert infer_sql_type([2.5, 1.0]) == "REAL"
    assert infer_sql_type(["a", "b"]) == "TEXT"
    assert infer_sql_type([1, None]) == "TEXT"
    assert infer_sql_type([True]) == "TEXT"
    assert infer_sql_type([]) == "TEXT"


def test_create_table_and_exists(conn: sqlite3.Connection) -> None:
    """建表后 table_exists 为真，重复建表抛 TableExistsError。."""
    create_table(conn, "t", ["a", "b"], ["INTEGER", "TEXT"])
    assert table_exists(conn, "t")
    with pytest.raises(TableExistsError, match="已存在"):
        create_table(conn, "t", ["a"], ["TEXT"])


def test_create_table_validates_arguments(conn: sqlite3.Connection) -> None:
    """建表参数校验：类型不合法/列数不一致/重复列名。."""
    with pytest.raises(ValueError, match="不一致"):
        create_table(conn, "t", ["a"], ["TEXT", "TEXT"])
    with pytest.raises(ValueError, match="至少需要一列"):
        create_table(conn, "t", [], [])
    with pytest.raises(ValueError, match="重复"):
        create_table(conn, "t", ["a", "a"], ["TEXT", "TEXT"])
    with pytest.raises(ValueError, match="非法列类型"):
        create_table(conn, "t", ["a"], ["BLOB"])


def test_insert_rows_batch_and_count(conn: sqlite3.Connection) -> None:
    """插入行计数正确且批量分片不影响结果。."""
    create_table(conn, "t", ["a", "b"], ["INTEGER", "TEXT"])
    rows = [(i, f"行{i}") for i in range(2500)]
    count = insert_rows(conn, "t", ["a", "b"], rows)
    assert count == 2500
    cur = conn.execute("SELECT COUNT(*) FROM t")
    assert cur.fetchone()[0] == 2500


def test_insert_empty_rows(conn: sqlite3.Connection) -> None:
    """空行迭代器插入 0 行不报错。."""
    create_table(conn, "t", ["a"], ["INTEGER"])
    assert insert_rows(conn, "t", ["a"], []) == 0


def test_table_infos_and_names(conn: sqlite3.Connection) -> None:
    """元数据查询：列信息/行数/表名排序。."""
    create_table(conn, "zeta", ["x"], ["INTEGER"])
    create_table(conn, "alpha", ["y", "z"], ["TEXT", "REAL"])
    insert_rows(conn, "zeta", ["x"], [(1,), (2,)])
    names = table_names(conn)
    assert names == ["alpha", "zeta"]
    infos = {t.name: t for t in table_infos(conn)}
    assert infos["zeta"].row_count == 2
    assert infos["alpha"].row_count == 0
    cols = infos["alpha"].columns
    assert [c.name for c in cols] == ["y", "z"]
    assert [c.sql_type for c in cols] == ["TEXT", "REAL"]


def test_column_infos_of_missing_table(conn: sqlite3.Connection) -> None:
    """不存在表的列信息为空列表。."""
    assert column_infos(conn, "nope") == []


def test_drop_table_idempotent(conn: sqlite3.Connection) -> None:
    """删表幂等：不存在时静默跳过。."""
    create_table(conn, "t", ["a"], ["TEXT"])
    drop_table(conn, "t")
    drop_table(conn, "t")  # 第二次不抛错
    assert not table_exists(conn, "t")


def test_find_free_table_name_suffixes(conn: sqlite3.Connection) -> None:
    """冲突表名依次尝试 base_2/base_3。."""
    create_table(conn, "demo", ["a"], ["TEXT"])
    create_table(conn, "demo_2", ["a"], ["TEXT"])
    assert find_free_table_name(conn, "free") == "free"
    assert find_free_table_name(conn, "demo") == "demo_3"
    with pytest.raises(ValueError, match="非法标识符"):
        find_free_table_name(conn, "bad name")


def test_fetch_preview_limits_rows(conn: sqlite3.Connection) -> None:
    """预览读取列名与前 N 行。."""
    create_table(conn, "t", ["a", "b"], ["INTEGER", "TEXT"])
    insert_rows(conn, "t", ["a", "b"], [(i, f"v{i}") for i in range(300)])
    names, rows = fetch_preview(conn, "t", limit=10)
    assert names == ["a", "b"]
    assert len(rows) == 10
    assert rows[0] == (0, "v0")
