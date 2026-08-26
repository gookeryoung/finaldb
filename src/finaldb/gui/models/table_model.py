"""表模型：工作区表列表（ListModel）与表预览（TableModel）。."""

from __future__ import annotations

from typing import Any

from PySide2.QtCore import QAbstractListModel, QAbstractTableModel, QByteArray, QModelIndex, Qt

__all__ = ["TableListModel", "TablePreviewModel"]

_ROLE_TABLE_NAME = QByteArray(b"name")
_ROLE_TABLE_ROWS = QByteArray(b"rows")
_ROLE_DISPLAY = QByteArray(b"display")

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


class TablePreviewModel(QAbstractTableModel):
    """表数据预览模型（前 N 行，QML TableView 绑定 ``model.display``）。."""

    def __init__(self, parent: object | None = None) -> None:
        """初始化空模型。."""
        super().__init__(parent)
        self._columns: list[str] = []
        self._rows: list[tuple[object, ...]] = []

    def roleNames(self) -> dict[int, QByteArray]:
        """只暴露 display 角色。."""
        return {Qt.DisplayRole: _ROLE_DISPLAY}

    def rowCount(self, parent: QModelIndex = _NO_PARENT) -> int:
        """行数。."""
        return 0 if parent.isValid() else len(self._rows)

    def columnCount(self, parent: QModelIndex = _NO_PARENT) -> int:
        """列数。."""
        return 0 if parent.isValid() else len(self._columns)

    def data(self, index: QModelIndex, role: int = Qt.DisplayRole) -> Any:
        """返回单元格显示文本（None 显示为空串）。."""
        if not index.isValid() or role != Qt.DisplayRole:
            return None
        if not (0 <= index.row() < len(self._rows)):
            return None
        row = self._rows[index.row()]
        col = index.column()
        if not (0 <= col < len(row)):
            return None
        value = row[col]
        return "" if value is None else str(value)

    def headerData(self, section: int, orientation: Qt.Orientation, role: int = Qt.DisplayRole) -> Any:
        """列头返回列名。."""
        if role == Qt.DisplayRole and orientation == Qt.Horizontal and 0 <= section < len(self._columns):
            return self._columns[section]
        return None

    def reset_data(self, columns: list[str], rows: list[tuple[object, ...]]) -> None:
        """整体替换预览数据并通知视图。."""
        self.beginResetModel()
        self._columns = list(columns)
        self._rows = list(rows)
        self.endResetModel()
