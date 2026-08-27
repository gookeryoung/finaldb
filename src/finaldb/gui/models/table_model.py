"""表模型：工作区表列表（ListModel）。."""

from __future__ import annotations

from typing import Any

from PySide2.QtCore import QAbstractListModel, QByteArray, QModelIndex, Qt

__all__ = ["TableListModel"]

_ROLE_TABLE_NAME = QByteArray(b"name")
_ROLE_TABLE_ROWS = QByteArray(b"rows")

# QModelIndex 为不可值类型，作默认参数的模块级单例（B008 规避）
_NO_PARENT = QModelIndex()


class TableListModel(QAbstractListModel):
    """当前工作区内的表列表（表名 + 行数）。."""

    def __init__(self, parent: object | None = None) -> None:
        """初始化空模型。."""
        super().__init__(parent)
        self._entries: list[tuple[str, int]] = []

    def roleNames(self) -> dict[int, QByteArray]:
        """声明角色名映射。."""
        return {Qt.UserRole + 1: _ROLE_TABLE_NAME, Qt.UserRole + 2: _ROLE_TABLE_ROWS}

    def rowCount(self, parent: QModelIndex = _NO_PARENT) -> int:
        """行数 = 表数量。."""
        return 0 if parent.isValid() else len(self._entries)

    def data(self, index: QModelIndex, role: int = Qt.DisplayRole) -> Any:
        """按角色返回表名/行数。."""
        if not index.isValid() or not (0 <= index.row() < len(self._entries)):
            return None

        name, rows = self._entries[index.row()]
        key = role - Qt.UserRole
        if key == 1:
            return name
        if key == 2:
            return rows
        return None

    def reload(self, entries: list[tuple[str, int]]) -> None:
        """整体替换数据并通知视图。."""
        self.beginResetModel()
        self._entries = list(entries)
        self.endResetModel()

    def table_at(self, row: int) -> str | None:
        """按行号取表名（越界返回 None）。."""
        if 0 <= row < len(self._entries):
            return self._entries[row][0]
        return None
