"""JSON 导入器：数组/对象数组/NDJSON/多表字典。."""

from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path
from typing import Any

from finaldb.core.exceptions import InvalidDataError
from finaldb.core.importers.base import TableData
from finaldb.core.importers.naming import sanitize_identifier

__all__ = ["read_json"]


def read_json(path: Path) -> Iterator[TableData]:
    """解析 JSON 文件为若干 TableData。

    支持结构（按优先级）：

    - 顶层 list：单表；元素为 dict → 键并集为列（按首见顺序），
      元素为 list → 生成 c1..cN 列
    - 顶层 dict 且值为 list：多表（每个键一张表，表名 = 文件名_键）

    :param path: 文件路径（.json / .ndjson）
    :return: TableData 迭代器
    :raises InvalidDataError: 顶层结构不支持或数据为空
    """
    if path.suffix.lower() == ".ndjson":
        records = _read_ndjson(path)
        yield _records_to_table(sanitize_identifier(path.stem), records)
        return
    try:
        data = json.loads(path.read_text("utf-8"))
    except (OSError, ValueError) as exc:
        raise InvalidDataError(f"JSON 解析失败: {path.name}: {exc}") from exc
    if isinstance(data, list):
        yield _records_to_table(sanitize_identifier(path.stem), data)
        return
    if isinstance(data, dict) and all(isinstance(v, list) for v in data.values()) and data:
        for key, records in data.items():
            yield _records_to_table(sanitize_identifier(f"{path.stem}_{key}"), records)
        return
    raise InvalidDataError(
        f"不支持的 JSON 结构（须为对象数组、行数组或多表字典）: {path.name}"
    )


def _read_ndjson(path: Path) -> list[dict[str, Any]]:
    """逐行解析 NDJSON 为 dict 列表。."""
    records = []
    for line_no, line in enumerate(path.read_text("utf-8").splitlines(), start=1):
        text = line.strip()
        if not text:
            continue
        try:
            item = json.loads(text)
        except ValueError as exc:
            raise InvalidDataError(f"NDJSON 第 {line_no} 行解析失败: {exc}") from exc
        if not isinstance(item, dict):
            raise InvalidDataError(f"NDJSON 第 {line_no} 行不是对象")
        records.append(item)
    if not records:
        raise InvalidDataError(f"文件为空: {path.name}")
    return records


def _records_to_table(table: str, records: list[Any]) -> TableData:
    """记录列表 → TableData（列序按首见顺序，缺失键补 None）。."""
    if not records:
        raise InvalidDataError(f"数据为空: {table}")
    if all(isinstance(r, dict) for r in records):
        columns: list[str] = []
        seen: set[str] = set()
        for rec in records:
            for key in rec:
                if key not in seen:
                    seen.add(key)
                    columns.append(key)
        dedup = _dedupe([sanitize_identifier(c) for c in columns])
        rows = [tuple(_normalize(rec.get(c)) for c in columns) for rec in records]
        return TableData(name=table, columns=dedup, rows=rows)
    if all(isinstance(r, list) for r in records):
        width = max(len(r) for r in records)
        cols = tuple(f"c{i + 1}" for i in range(width))
        rows = [tuple(list(r) + [None] * (width - len(r))) for r in records]
        return TableData(name=table, columns=cols, rows=rows)
    raise InvalidDataError(f"数组元素类型不一致（须全为对象或全为数组）: {table}")


def _dedupe(columns: list[str]) -> tuple[str, ...]:
    """列名去重（后缀 _2/_3）。."""
    seen: dict[str, int] = {}
    result = []
    for col in columns:
        if col in seen:
            seen[col] += 1
            result.append(f"{col}_{seen[col]}")
        else:
            seen[col] = 1
            result.append(col)
    return tuple(result)


def _normalize(value: Any) -> object:
    """标量直接返回；嵌套结构序列化为 JSON 文本。."""
    if value is None or isinstance(value, (bool, int, float, str)):
        if isinstance(value, str) and not value.strip():
            return None
        return value
    return json.dumps(value, ensure_ascii=False)
