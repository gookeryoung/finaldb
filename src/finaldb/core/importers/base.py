"""导入数据容器：统一各格式解析结果的中间表示。."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

__all__ = ["TableData"]


@dataclass(frozen=True)
class TableData:
    """单个待导入表的解析结果。

    :ivar name: 建议表名（合法标识符）
    :ivar columns: 列名列表（已清洗为合法标识符）
    :ivar rows: 行迭代器（惰性，每行与 columns 等长）
    """

    name: str
    columns: tuple[str, ...]
    rows: Iterable[tuple[object, ...]]
