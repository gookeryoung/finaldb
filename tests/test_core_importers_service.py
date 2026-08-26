"""导入服务测试：格式分发 + 落库 + 表名去重。."""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Iterator
from pathlib import Path

import pytest

from finaldb.core.exceptions import UnsupportedFormatError
from finaldb.core.importers.service import import_file, import_into_workspace
from finaldb.core.storage.database import table_names


@pytest.fixture()
def conn(tmp_path: Path) -> Iterator[sqlite3.Connection]:
    """临时数据库连接。."""
    c = sqlite3.connect(str(tmp_path / "ws.db"))
    yield c
    c.close()


def _write_csv(path: Path) -> Path:
    """写入标准 CSV。."""
    path.write_text("id,score\n1,9.5\n2,8.0\n", "utf-8")
    return path


def test_import_file_dispatches_by_suffix(tmp_path: Path) -> None:
    """按扩展名分发到对应解析器。."""
    td = next(iter(import_file(_write_csv(tmp_path / "a.csv"))))
    assert td.columns == ("id", "score")
    j = tmp_path / "b.json"
    j.write_text(json.dumps([{"x": 1}]), "utf-8")
    td2 = next(iter(import_file(j)))
    assert td2.columns == ("x",)


def test_import_file_tsv(tmp_path: Path) -> None:
    """TSV 走制表符分隔。."""
    f = tmp_path / "t.tsv"
    f.write_text("a\tb\n1\t2\n", "utf-8")
    td = next(iter(import_file(f)))
    assert list(td.rows) == [(1, 2)]


def test_import_file_unknown_suffix(tmp_path: Path) -> None:
    """未知扩展名报不支持。."""
    f = tmp_path / "d.parquet"
    f.write_bytes(b"x")
    with pytest.raises(UnsupportedFormatError, match="不支持的文件格式"):
        list(import_file(f))


def test_import_into_workspace_creates_table(conn: sqlite3.Connection, tmp_path: Path) -> None:
    """导入落库：类型推断 + 行数统计。."""
    results = import_into_workspace(conn, _write_csv(tmp_path / "a.csv"))
    assert len(results) == 1
    assert results[0].table == "a"
    assert results[0].rows == 2
    assert results[0].source == "a.csv"
    assert table_names(conn) == ["a"]
    cur = conn.execute("PRAGMA table_info(a)")
    types = [row[2] for row in cur.fetchall()]
    assert types == ["INTEGER", "REAL"]
    cur = conn.execute("SELECT * FROM a ORDER BY id")
    assert cur.fetchall() == [(1, 9.5), (2, 8.0)]


def test_import_name_conflict_gets_suffix(conn: sqlite3.Connection, tmp_path: Path) -> None:
    """表名冲突自动加后缀 _2。."""
    import_into_workspace(conn, _write_csv(tmp_path / "a.csv"))
    # 同名文件放子目录，确保 stem 相同触发冲突
    sub = tmp_path / "sub"
    sub.mkdir()
    results = import_into_workspace(conn, _write_csv(sub / "a.csv"))
    assert results[0].table == "a_2"
    assert table_names(conn) == ["a", "a_2"]


def test_import_multi_sheet_excel(conn: sqlite3.Connection, tmp_path: Path) -> None:
    """Excel 多 sheet 全部落库。."""
    from openpyxl import Workbook

    wb = Workbook()
    ws1 = wb.active
    assert ws1 is not None
    ws1.append(["x"])
    ws1.append([1])
    ws2 = wb.create_sheet("two")
    ws2.append(["y"])
    ws2.append([2])
    path = tmp_path / "m.xlsx"
    wb.save(path)
    results = import_into_workspace(conn, path)
    assert [r.table for r in results] == ["m_Sheet", "m_two"]
    assert all(r.rows == 1 for r in results)


def test_import_more_than_sample_rows(conn: sqlite3.Connection, tmp_path: Path) -> None:
    """行数超过类型采样窗口（200 行）时全量落库。."""
    lines = ["n"] + [str(i) for i in range(600)]
    f = tmp_path / "big.csv"
    f.write_text("\n".join(lines), "utf-8")
    results = import_into_workspace(conn, f)
    assert results[0].rows == 600
    cur = conn.execute("SELECT COUNT(*) FROM big")
    assert cur.fetchone()[0] == 600
