"""CSV/TSV 导入器测试。."""

from __future__ import annotations

from pathlib import Path

import pytest

from finaldb.core.exceptions import InvalidDataError
from finaldb.core.importers.csv_reader import read_csv


def _write(path: Path, content: str, encoding: str = "utf-8") -> Path:
    """写入临时文件。."""
    path.write_text(content, encoding)
    return path


def test_basic_csv_with_header(tmp_path: Path) -> None:
    """标准 CSV：首行表头，数值列解析。."""
    f = _write(tmp_path / "data.csv", "id,name\n1,甲\n2,乙\n")
    td = read_csv(f)
    assert td.name == "data"
    assert td.columns == ("id", "name")
    assert list(td.rows) == [(1, "甲"), (2, "乙")]


def test_csv_without_header(tmp_path: Path) -> None:
    """无表头（表头全空）时生成 c1..cN 列并保留首行数据。."""
    f = _write(tmp_path / "raw.csv", "\n10,甲\n20,乙\n")
    td = read_csv(f)
    assert td.columns == ("c1", "c2")
    assert list(td.rows) == [(10, "甲"), (20, "乙")]


def test_csv_skips_blank_lines(tmp_path: Path) -> None:
    """空行被跳过，不产生数据行。."""
    f = _write(tmp_path / "d.csv", "a,b\n1,x\n\n3,z\n")
    td = read_csv(f)
    assert list(td.rows) == [(1, "x"), (3, "z")]


def test_csv_pads_and_truncates_rows(tmp_path: Path) -> None:
    """缺列补 None，多列截断到表头宽度。."""
    f = _write(tmp_path / "d.csv", "a,b,c\n1\n2,3,4,5\n")
    td = read_csv(f)
    rows = list(td.rows)
    assert rows[0] == (1, None, None)
    assert rows[1] == (2, 3, 4)


def test_csv_duplicate_headers_get_suffix(tmp_path: Path) -> None:
    """重复表头自动去重加后缀。."""
    f = _write(tmp_path / "d.csv", "id,id\n1,2\n")
    td = read_csv(f)
    assert td.columns == ("id", "id_2")


def test_csv_tsv_delimiter(tmp_path: Path) -> None:
    """TSV 用制表符分隔。."""
    f = _write(tmp_path / "d.tsv", "a\tb\n1\t2\n")
    td = read_csv(f, delimiter="\t")
    assert list(td.rows) == [(1, 2)]


def test_csv_gbk_encoding(tmp_path: Path) -> None:
    """GBK 编码文件可回退解析。."""
    f = tmp_path / "gbk.csv"
    f.write_bytes("名字,值\n甲,1\n".encode("gbk"))
    td = read_csv(f)
    assert list(td.rows) == [("甲", 1)]


def test_csv_bom_encoding(tmp_path: Path) -> None:
    """UTF-8 BOM 文件表头无残留 BOM 字符。."""
    f = tmp_path / "bom.csv"
    f.write_bytes("a,b\n1,2\n".encode("utf-8-sig"))
    td = read_csv(f)
    assert td.columns == ("a", "b")


def test_csv_float_parsing(tmp_path: Path) -> None:
    """数值文本解析：int/float，非数值保留原文。."""
    f = _write(tmp_path / "d.csv", "a,b,c\n1,2.5,x\n")
    td = read_csv(f)
    assert list(td.rows) == [(1, 2.5, "x")]


def test_csv_empty_file_raises(tmp_path: Path) -> None:
    """空文件报 InvalidDataError。."""
    f = _write(tmp_path / "empty.csv", "")
    with pytest.raises(InvalidDataError, match="为空"):
        read_csv(f)


def test_csv_header_only_yields_no_rows(tmp_path: Path) -> None:
    """只有表头时产出 0 行（合法空表）。."""
    f = _write(tmp_path / "d.csv", "a,b\n")
    td = read_csv(f)
    assert list(td.rows) == []
