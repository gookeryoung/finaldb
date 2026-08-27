"""导入服务：按扩展名分发解析器，并把 TableData 落库。."""

from __future__ import annotations

import sqlite3
from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from itertools import islice
from pathlib import Path

from finaldb.core.exceptions import UnsupportedFormatError
from finaldb.core.importers.base import TableData
from finaldb.core.importers.csv_reader import read_csv
from finaldb.core.importers.excel_reader import read_excel, supports_excel
from finaldb.core.importers.json_reader import read_json
from finaldb.core.storage.database import (
    create_table,
    find_free_table_name,
    infer_sql_type,
    insert_rows,
)

__all__ = ["ImportResult", "import_file", "import_into_workspace"]

# 类型推断的采样行数
_TYPE_SAMPLE_ROWS = 200


@dataclass(frozen=True)
class ImportResult:
    """单表导入结果。

    :ivar table: 实际落库表名（可能带去重后缀）
    :ivar rows: 导入行数
    :ivar source: 来源文件名
    """

    table: str
    rows: int
    source: str


def import_file(path: Path) -> Iterator[TableData]:
    """按扩展名识别格式并解析文件（不落库）。

    :param path: 数据文件路径
    :return: TableData 迭代器（CSV/JSON 单个，Excel 多 sheet 多个）
    :raises UnsupportedFormatError: 扩展名不受支持
    """
    suffix = path.suffix.lower()
    if suffix in (".csv", ".tsv"):
        delimiter = "\t" if suffix == ".tsv" else ","
        yield read_csv(path, delimiter=delimiter)
    elif supports_excel(suffix) or suffix == ".xls":
        yield from read_excel(path)
    elif suffix in (".json", ".ndjson"):
        yield from read_json(path)
    else:
        raise UnsupportedFormatError(f"不支持的文件格式: {path.suffix}")


def import_into_workspace(conn: sqlite3.Connection, path: Path) -> list[ImportResult]:
    """解析文件并全部落库（表名冲突自动加后缀）。

    :param conn: 工作区数据库连接
    :param path: 数据文件路径
    :return: 各表导入结果列表
    """
    results = []
    for table_data in import_file(path):
        results.append(_import_table(conn, table_data, path.name))
    return results


def _import_table(conn: sqlite3.Connection, data: TableData, source: str) -> ImportResult:
    """单个 TableData 落库：类型推断采样 + 冲突改名 + 批量写入。

    :param conn: 数据库连接
    :param data: 解析结果
    :param source: 来源文件名（记录用）
    :return: 导入结果
    """
    if not data.columns:
        raise UnsupportedFormatError(f"数据无列: {source}")
    table = find_free_table_name(conn, data.name)
    # 先统一为迭代器再采样：rows 契约为 Iterable（JSON 传 list、CSV/Excel 传生成器），
    # 直接对 list 做 islice 不会推进它，后续 rest 会把采样行重复入库
    rows_iter = iter(data.rows)
    sample = list(islice(rows_iter, _TYPE_SAMPLE_ROWS))
    sql_types = [_infer_column_type(sample, i) for i in range(len(data.columns))]
    create_table(conn, table, list(data.columns), sql_types)
    chained = _chain_iterables(iter(sample), rows_iter)
    count = insert_rows(conn, table, list(data.columns), chained)
    return ImportResult(table=table, rows=count, source=source)


def _infer_column_type(sample: list[tuple[object, ...]], index: int) -> str:
    """根据采样行推断指定列的 SQL 类型（列越界按空样本处理）。."""
    values = [row[index] for row in sample if index < len(row)]
    return infer_sql_type(values)


def _chain_iterables(
    first: Iterator[tuple[object, ...]],
    rest: Iterable[tuple[object, ...]],
) -> Iterator[tuple[object, ...]]:
    """串联两个行迭代器（采样行 + 剩余行）。."""
    yield from first
    yield from rest
