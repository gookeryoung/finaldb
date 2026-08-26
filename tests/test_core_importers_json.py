"""JSON/NDJSON 导入器测试。."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from finaldb.core.exceptions import InvalidDataError
from finaldb.core.importers.json_reader import read_json


def test_json_object_array(tmp_path: Path) -> None:
    """对象数组：列按首见顺序，缺失键补 None。."""
    f = tmp_path / "data.json"
    f.write_text(json.dumps([{"a": 1, "b": "x"}, {"a": 2}]), "utf-8")
    td = next(iter(read_json(f)))
    assert td.name == "data"
    assert td.columns == ("a", "b")
    assert list(td.rows) == [(1, "x"), (2, None)]


def test_json_nested_values_stringified(tmp_path: Path) -> None:
    """嵌套结构序列化为 JSON 文本，空白字符串归一为 None。."""
    f = tmp_path / "data.json"
    f.write_text(json.dumps([{"cfg": {"k": 1}, "blank": "  "}], ensure_ascii=False), "utf-8")
    td = next(iter(read_json(f)))
    assert list(td.rows) == [('{"k": 1}', None)]


def test_json_row_arrays(tmp_path: Path) -> None:
    """行数组：生成 c1..cN 列并按最长行补齐。."""
    f = tmp_path / "data.json"
    f.write_text(json.dumps([[1, "x"], [2]]), "utf-8")
    td = next(iter(read_json(f)))
    assert td.columns == ("c1", "c2")
    assert list(td.rows) == [(1, "x"), (2, None)]


def test_json_multi_table_dict(tmp_path: Path) -> None:
    """多表字典：每个键一张表，表名 = 文件名_键。."""
    f = tmp_path / "book.json"
    payload = {"users": [{"id": 1}], "orders": [{"oid": 9}]}
    f.write_text(json.dumps(payload), "utf-8")
    tables = {td.name: td for td in read_json(f)}
    assert set(tables) == {"book_users", "book_orders"}
    assert list(tables["book_users"].rows) == [(1,)]


def test_ndjson_records(tmp_path: Path) -> None:
    """NDJSON：逐行对象，跳过空行。."""
    f = tmp_path / "log.ndjson"
    f.write_text('{"a": 1}\n\n{"a": 2}\n', "utf-8")
    td = next(iter(read_json(f)))
    assert td.name == "log"
    assert list(td.rows) == [(1,), (2,)]


def test_json_unsupported_structure(tmp_path: Path) -> None:
    """顶层标量报不支持结构。."""
    f = tmp_path / "scalar.json"
    f.write_text("42", "utf-8")
    with pytest.raises(InvalidDataError, match="不支持的 JSON 结构"):
        list(read_json(f))


def test_json_mixed_array_types(tmp_path: Path) -> None:
    """数组元素类型混杂报错。."""
    f = tmp_path / "mix.json"
    f.write_text(json.dumps([{"a": 1}, [1, 2]]), "utf-8")
    with pytest.raises(InvalidDataError, match="不一致"):
        list(read_json(f))


def test_json_invalid_file(tmp_path: Path) -> None:
    """非法 JSON 报解析失败。."""
    f = tmp_path / "bad.json"
    f.write_text("{ broken", "utf-8")
    with pytest.raises(InvalidDataError, match="解析失败"):
        list(read_json(f))


def test_json_empty_array(tmp_path: Path) -> None:
    """空数组报数据为空。."""
    f = tmp_path / "empty.json"
    f.write_text("[]", "utf-8")
    with pytest.raises(InvalidDataError, match="为空"):
        list(read_json(f))


def test_ndjson_bad_line(tmp_path: Path) -> None:
    """NDJSON 某行非法时报行号。."""
    f = tmp_path / "bad.ndjson"
    f.write_text('{"a": 1}\nnot json\n', "utf-8")
    with pytest.raises(InvalidDataError, match="第 2 行"):
        list(read_json(f))


def test_json_bool_preserved(tmp_path: Path) -> None:
    """布尔值原样保留（不做数值转换）。."""
    f = tmp_path / "flags.json"
    f.write_text(json.dumps([{"ok": True, "no": False}]), "utf-8")
    td = next(iter(read_json(f)))
    assert list(td.rows) == [(True, False)]
