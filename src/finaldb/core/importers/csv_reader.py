"""CSV/TSV 导入器：编码探测 + 分隔符按扩展名选择。."""

from __future__ import annotations

import csv
from collections.abc import Iterator
from pathlib import Path

from finaldb.core.exceptions import InvalidDataError
from finaldb.core.importers.base import TableData
from finaldb.core.importers.naming import sanitize_identifier

__all__ = ["read_csv"]

# 尝试的编码列表：utf-8-sig 兼容 BOM，gbk 兼容国内导出的 Excel CSV
_ENCODINGS = ("utf-8-sig", "gbk")


def read_csv(path: Path, delimiter: str = ",") -> TableData:
    """解析 CSV/TSV 文件为 TableData（惰性行迭代器）。

    :param path: 文件路径
    :param delimiter: 列分隔符（CSV 逗号 / TSV 制表符）
    :return: 首行为表头的解析结果
    :raises InvalidDataError: 文件为空或无数据行
    """
    for encoding in _ENCODINGS:
        try:
            text_lines = path.read_text(encoding).splitlines(keepends=True)
            break
        except UnicodeDecodeError:
            continue
    else:
        raise InvalidDataError(f"无法识别文件编码: {path.name}")
    if not text_lines:
        raise InvalidDataError(f"文件为空: {path.name}")
    reader = csv.reader(iter(text_lines), delimiter=delimiter)
    header = next(reader, None)
    if header is None:
        raise InvalidDataError(f"文件为空: {path.name}")
    if any(cell.strip() for cell in header):
        columns = _dedupe_columns(header)
    else:
        # 无表头：首行即数据，生成 c1..cN 列名
        first_row = next(reader, None)
        if first_row is None:
            raise InvalidDataError(f"文件为空: {path.name}")
        width = len(first_row)
        columns = tuple(f"c{i + 1}" for i in range(width))
        reader = _chain_row(first_row, reader)
    table = sanitize_identifier(path.stem)
    return TableData(name=table, columns=columns, rows=_rows_of(reader, len(columns)))


def _dedupe_columns(header: list[str]) -> tuple[str, ...]:
    """清洗表头为合法且不重复的列名。

    :param header: 原始表头单元格
    :return: 清洗后的列名元组
    """
    cleaned = [sanitize_identifier(c.strip()) for c in header]
    seen: dict[str, int] = {}
    result = []
    for col in cleaned:
        if col in seen:
            seen[col] += 1
            result.append(f"{col}_{seen[col]}")
        else:
            seen[col] = 1
            result.append(col)
    return tuple(result)


def _chain_row(
    first: list[str], reader: csv.reader
) -> Iterator[list[str]]:
    """把已取出的首行重新接回迭代器头部。

    :param first: 首行数据
    :param reader: 其余行的 CSV reader
    :return: 首行 + 其余行的迭代器
    """
    yield first
    yield from reader


def _rows_of(reader: csv.reader, width: int) -> Iterator[tuple[object, ...]]:
    """把 CSV 行转为定宽元组（缺列补 None，多列截断）。

    :param reader: CSV reader
    :param width: 期望列数
    :return: 行元组迭代器
    """
    for row in reader:
        if not row or (len(row) == 1 and not row[0].strip()):
            continue  # 跳过空行
        vals: list[object] = [_parse_cell(c) for c in row[:width]]
        while len(vals) < width:
            vals.append(None)
        yield tuple(vals)


def _parse_cell(cell: str) -> object:
    """单元格文本尽量解析为数值，失败保留原文。

    :param cell: 单元格文本
    :return: int / float / str
    """
    text = cell.strip()
    if not text:
        return None
    try:
        return int(text)
    except ValueError:
        pass
    try:
        return float(text)
    except ValueError:
        return cell
