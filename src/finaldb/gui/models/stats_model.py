"""统计条目模型：QML 统计页的表分布展示。."""

from __future__ import annotations

from typing import Any

from PySide2.QtCore import QAbstractListModel, QByteArray, QModelIndex, Qt

from finaldb.core.storage.database import TableInfo

__all__ = ["TableStatModel"]

_NO_PARENT = QModelIndex()

# 角色名（QML delegate 通过 model.角色名 取值）
_ROLE_NAME = QByteArray(b"name")
_ROLE_ROWS = QByteArray(b"rows")
_ROLE_COLUMNS = QByteArray(b"columns")
_ROLE_DISPLAY = QByteArray(b"display")
_ROLE_RATIO = QByteArray(b"ratio")


class TableStatModel(QAbstractListModel):
    """表统计列表模型（每行 = 一张表的行数/列数摘要）。."""

    def __init__(self, parent: object | None = None) -> None:
        """初始化空列表。."""
        super().__init__(parent)
        self._infos: list[TableInfo] = []

    def roleNames(self) -> dict[int, QByteArray]:
        """声明 QML 角色名。."""
        return {
            Qt.UserRole + 1: _ROLE_NAME,
            Qt.UserRole + 2: _ROLE_ROWS,
            Qt.UserRole + 3: _ROLE_COLUMNS,
            Qt.UserRole + 4: _ROLE_DISPLAY,
            Qt.UserRole + 5: _ROLE_RATIO,
        }

    def rowCount(self, parent: QModelIndex = _NO_PARENT) -> int:
        """条目数（扁平列表无子级）。."""
        return 0 if parent.isValid() else len(self._infos)

    def data(self, index: QModelIndex, role: int = Qt.DisplayRole) -> Any:
        """按角色返回条目数据（越界/未知角色返回 None）。."""
        if not index.isValid() or not (0 <= index.row() < len(self._infos)):
            return None
        info = self._infos[index.row()]
        values: dict[QByteArray, Any] = {
            _ROLE_NAME: info.name,
            _ROLE_ROWS: info.row_count,
            _ROLE_COLUMNS: len(info.columns),
            _ROLE_DISPLAY: f"{info.name}（{len(info.columns)} 列 / {info.row_count} 行）",
            _ROLE_RATIO: self._ratio_of(info),
        }
        return values.get(self.roleNames().get(role))

    def reload(self, infos: list[TableInfo]) -> None:
        """整表替换并刷新。."""
        self.beginResetModel()
        self._infos = list(infos)
        self.endResetModel()

    def stat_at(self, row: int) -> TableInfo | None:
        """按行号取表统计（越界返回 None）。."""
        if 0 <= row < len(self._infos):
            return self._infos[row]
        return None

    def max_rows(self) -> int:
        """全部表中的最大行数（条形图比例基准）。."""
        return max((info.row_count for info in self._infos), default=0)

    def _ratio_of(self, info: TableInfo) -> float:
        """单表行数相对最大行数的占比（0.0~1.0）。."""
        max_rows = self.max_rows()
        return info.row_count / max_rows if max_rows > 0 else 0.0
