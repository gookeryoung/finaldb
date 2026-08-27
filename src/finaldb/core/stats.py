"""工作区统计分析：表级概览与列级统计（纯 Python，不依赖 GUI）。

面向统计页的数据源：工作区整体规模（表数/行数/列数/库体积）与
单表每列的质量画像（空值/唯一值/最值/均值），全部走 SQLite 聚合查询。
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from finaldb.core.storage.database import (
    column_infos,
    quote_identifier,
    row_count_of,
    table_infos,
)

__all__ = [
    "ColumnStat",
    "WorkspaceOverview",
    "column_stats",
    "format_size",
    "workspace_overview",
]

# 数值类型集合（计算均值；TEXT 列均值无意义跳过）
_NUMERIC_TYPES = {"INTEGER", "REAL", "NUMERIC"}


@dataclass(frozen=True)
class ColumnStat:
    """单列统计画像。

    :ivar name: 列名
    :ivar sql_type: 列类型（INTEGER/REAL/TEXT）
    :ivar total: 表总行数
    :ivar non_null: 非空值数
    :ivar null_count: 空值数
    :ivar distinct_count: 唯一值数（NULL 不计入）
    :ivar minimum: 最小值（数值或文本比较；全空为 None）
    :ivar maximum: 最大值
    :ivar mean: 数值列均值（非数值列或全空为 None）
    """

    name: str
    sql_type: str
    total: int
    non_null: int
    null_count: int
    distinct_count: int
    minimum: object
    maximum: object
    mean: Optional[float]


@dataclass(frozen=True)
class WorkspaceOverview:
    """工作区整体规模概览。

    :ivar table_count: 表数
    :ivar total_rows: 全部表行数合计
    :ivar total_columns: 全部表列数合计
    :ivar db_bytes: data.db 文件体积（字节；文件不存在为 0）
    """

    table_count: int
    total_rows: int
    total_columns: int
    db_bytes: int


def workspace_overview(conn: sqlite3.Connection, db_path: Path) -> WorkspaceOverview:
    """统计工作区整体规模。

    :param conn: 数据库连接
    :param db_path: data.db 文件路径（用于体积统计）
    :return: 概览数据对象
    """
    infos = table_infos(conn)
    return WorkspaceOverview(
        table_count=len(infos),
        total_rows=sum(info.row_count for info in infos),
        total_columns=sum(len(info.columns) for info in infos),
        db_bytes=db_path.stat().st_size if db_path.is_file() else 0,
    )


def column_stats(conn: sqlite3.Connection, table: str) -> list[ColumnStat]:
    """统计指定表全部列的画像（每列一次聚合查询）。

    :param conn: 数据库连接
    :param table: 表名
    :return: 按列序排列的统计列表（表不存在返回空列表）
    """
    infos = column_infos(conn, table)
    if not infos:
        return []
    total = row_count_of(conn, table)
    stats: list[ColumnStat] = []
    for info in infos:
        col = quote_identifier(info.name)
        tbl = quote_identifier(table)
        non_null, distinct, minimum, maximum = conn.execute(
            f"SELECT COUNT({col}), COUNT(DISTINCT {col}), MIN({col}), MAX({col}) FROM {tbl}"
        ).fetchone()
        mean: Optional[float] = None
        if info.sql_type in _NUMERIC_TYPES:
            avg = conn.execute(f"SELECT AVG({col}) FROM {tbl}").fetchone()[0]
            if avg is not None:
                mean = round(float(avg), 4)
        stats.append(
            ColumnStat(
                name=info.name,
                sql_type=info.sql_type,
                total=total,
                non_null=int(non_null),
                null_count=total - int(non_null),
                distinct_count=int(distinct),
                minimum=minimum,
                maximum=maximum,
                mean=mean,
            )
        )
    return stats


def format_size(num_bytes: int) -> str:
    """字节数格式化为可读体积（B/KB/MB/GB）。

    :param num_bytes: 字节数
    :return: 保留一位小数的体积文本
    """
    if num_bytes < 1024:
        return f"{num_bytes} B"
    size = float(num_bytes)
    for unit in ("KB", "MB", "GB", "TB"):
        size /= 1024
        if size < 1024:
            return f"{size:.1f} {unit}"
    return f"{size:.1f} TB"
