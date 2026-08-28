"""自增键规则测试：存储层规则 + 服务层自动填键 + 元表隐藏。."""

from __future__ import annotations

from pathlib import Path

import pytest

from finaldb.core.editing import EditService
from finaldb.core.storage.database import connect, table_infos
from finaldb.core.storage.editing import insert_row
from finaldb.core.storage.keys import (
    clear_key_rule,
    get_key_rule,
    next_key,
    set_key_rule,
)


@pytest.fixture()
def db(tmp_path: Path) -> Path:
    """构造含示例表的数据库文件。."""
    path = tmp_path / "data.db"
    conn = connect(path)
    conn.execute("CREATE TABLE t (id INTEGER, name TEXT)")
    insert_row(conn, "t", [1, "a"])
    insert_row(conn, "t", [3, "b"])
    conn.close()
    return path


def test_rule_roundtrip(db: Path) -> None:
    """规则定义/读取/清除回环。."""
    conn = connect(db)
    assert get_key_rule(conn, "t") is None
    set_key_rule(conn, "t", "id", 1)
    assert get_key_rule(conn, "t") == ("id", 4)  # max(起始1, 已存3+1)
    clear_key_rule(conn, "t")
    assert get_key_rule(conn, "t") is None
    conn.close()


def test_next_key_avoids_reuse(db: Path) -> None:
    """删除最大键行后下一键不重号（存储计数器推进）。."""
    conn = connect(db)
    set_key_rule(conn, "t", "id", 1)
    assert next_key(conn, "t", "id") == 4
    assert next_key(conn, "t", "id") == 5
    conn.execute("DELETE FROM t WHERE id = 3")
    conn.commit()
    assert next_key(conn, "t", "id") == 6  # 不回退复用 4
    conn.close()


def test_next_key_without_rule(db: Path) -> None:
    """未定义规则或键列不匹配时返回 None。."""
    conn = connect(db)
    assert next_key(conn, "t", "id") is None
    set_key_rule(conn, "t", "id", 1)
    assert next_key(conn, "t", "name") is None
    conn.close()


def test_meta_table_hidden(db: Path) -> None:
    """键规则元表不出现在用户表清单。."""
    conn = connect(db)
    set_key_rule(conn, "t", "id", 1)
    names = [info.name for info in table_infos(conn)]
    assert "_finaldb_keycfg" not in names
    assert names == ["t"]
    conn.close()


def test_service_add_row_autofills_key(db: Path) -> None:
    """服务层追加行自动生成键序号；撤销后计数不回退。."""
    service = EditService(db)
    service.set_key_rule("t", "id", 1)
    rowid = service.add_row("t")
    names, rows, _ = service.fetch_page("t", 0)
    values = dict(rows)[rowid]
    assert values[names.index("id")] == 4  # max(1, 3+1)
    service.add_row("t")
    _, rows2, _ = service.fetch_page("t", 0)
    ids = [row[1][0] for row in rows2]
    assert ids == [1, 3, 4, 5]
    service.undo()
    service.add_row("t")
    _, rows3, _ = service.fetch_page("t", 0)
    assert [row[1][0] for row in rows3] == [1, 3, 4, 6]  # 撤销后新行仍不复用 5


def test_service_set_rule_bad_column(db: Path) -> None:
    """键列不存在时定义规则抛 ValueError。."""
    service = EditService(db)
    with pytest.raises(ValueError, match="列不存在"):
        service.set_key_rule("t", "nope", 1)
