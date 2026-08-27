"""列统计表模型：单表每列画像的二维表展示（嵌入统计页）。."""

from __future__ import annotations

from typing import Any

from PySide2.QtCore import QAbstractTableModel, QModelIndex, Qt

from finaldb.core.stats import ColumnStat

__all__ = ["ColumnStatModel"]

_NO_PARENT = QModelIndex()

# 表头：与 ColumnStat 字段一一对应（均值仅数值列有值）
_HEADERS = ("列名", "类型", "非空", "空值", "唯一值", "最小值", "最大值", "平均值")


class ColumnStatModel(QAbstractTableModel):
    """列统计二维表模型（每行 = 一列的统计画像）。."""

    def __init__(self, parent: object | None = None) -> None:
        """初始化空模型。."""
        super().__init__(parent)
        self._stats: list[ColumnStat] = []

    # ----------------------------- Qt 模型协议 -----------------------------

    def rowCount(self, parent: QModelIndex = _NO_PARENT) -> int:
        """行数。."""
        return 0 if parent.isValid() else len(self._stats)

    def columnCount(self, parent: QModelIndex = _NO_PARENT) -> int:
        """列数（固定统计字段数）。."""
        return 0 if parent.isValid() else len(_HEADERS)

    def data(self, index: QModelIndex, role: int = Qt.DisplayRole) -> Any:
        """返回统计单元格文本（None 显示为空串）。."""
        if not index.isValid() or role != Qt.DisplayRole:
            return None
        if not (0 <= index.row() < len(self._stats)):
            return None
        stat = self._stats[index.row()]
        values: tuple[object, ...] = (
            stat.name,
            stat.sql_type,
            stat.non_null,
            stat.null_count,
            stat.distinct_count,
            stat.minimum,
            stat.maximum,
            stat.mean,
        )
        col = index.column()
        if not (0 <= col < len(values)):
            return None
        value = values[col]
        return "" if value is None else str(value)

    def headerData(self, section: int, orientation: Qt.Orientation, role: int = Qt.DisplayRole) -> Any:
        """行号列头/列表头文本。."""
        if role != Qt.DisplayRole:
            return None
        if orientation == Qt.Horizontal and 0 <= section < len(_HEADERS):
            return _HEADERS[section]
        return None

    # ----------------------------- 数据装载 -----------------------------

    def reload(self, stats: list[ColumnStat]) -> None:
        """整体替换统计列表并通知视图。."""
        self.beginResetModel()
        self._stats = list(stats)
        self.endResetModel()

    def stat_at(self, row: int) -> ColumnStat | None:
        """按行号取统计对象（越界返回 None）。."""
        if 0 <= row < len(self._stats):
            return self._stats[row]
        return None
