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


def test_next_key_follows_data(db: Path) -> None:
    """下一键由数据驱动：删除最大键行后序号回落复用（双向绑定）。."""
    conn = connect(db)
    set_key_rule(conn, "t", "id", 1)
    assert next_key(conn, "t", "id") == 4
    assert next_key(conn, "t", "id") == 4  # 未落库前不推进
    conn.execute("DELETE FROM t WHERE id = 3")
    conn.commit()
    assert next_key(conn, "t", "id") == 2  # 删除后回落（剩余 id=1，下一为 2）
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
    """服务层追加行自动生成键序号；撤销/删除后序号随数据回落。."""
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
    assert [row[1][0] for row in rows3] == [1, 3, 4, 5]  # 撤销删 5 后新行复用 5


def test_service_delete_rows_then_reuse_key(db: Path) -> None:
    """用户场景回归：定义键规则后新增三行再删除，下一序号回落复用。."""
    service = EditService(db)
    service.set_key_rule("t", "id", 1)
    # 连续追加三行：键序号 4/5/6
    rowids = [service.add_row("t") for _ in range(3)]
    _, rows, _ = service.fetch_page("t", 0)
    assert [row[1][0] for row in rows] == [1, 3, 4, 5, 6]
    # 删除最后三行（键 4/5/6）
    service.delete_rows("t", rowids)
    _, rows2, _ = service.fetch_page("t", 0)
    assert [row[1][0] for row in rows2] == [1, 3]
    # 下一序号回落到 4，且规则查询（界面规则条同源）与实际生成一致
    assert service.key_rule("t") == ("id", 4)
    service.add_row("t")
    _, rows3, _ = service.fetch_page("t", 0)
    assert [row[1][0] for row in rows3] == [1, 3, 4]


def test_service_set_rule_bad_column(db: Path) -> None:
    """键列不存在时定义规则抛 ValueError。."""
    service = EditService(db)
    with pytest.raises(ValueError, match="列不存在"):
        service.set_key_rule("t", "nope", 1)
