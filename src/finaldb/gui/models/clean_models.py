"""清洗模型：规则列表、列名列表与清洗预览（TableModel）。."""

from __future__ import annotations

from typing import Any

from PySide2.QtCore import QAbstractListModel, QAbstractTableModel, QByteArray, QModelIndex, Qt

from finaldb.core.cleaning.rules import CleanRule

__all__ = ["CleanPreviewModel", "CleanRuleListModel", "StringListModel"]

_ROLE_KIND = QByteArray(b"kind")
_ROLE_COLUMN = QByteArray(b"column")
_ROLE_VALUE = QByteArray(b"value")
_ROLE_REPLACEMENT = QByteArray(b"replacement")
_ROLE_CASE_MODE = QByteArray(b"caseMode")
_ROLE_DISPLAY = QByteArray(b"display")
_ROLE_TEXT = QByteArray(b"text")

# QModelIndex 为不可值类型，作默认参数的模块级单例（B008 规避）
_NO_PARENT = QModelIndex()


class CleanRuleListModel(QAbstractListModel):
    """已配置的清洗规则列表（QML 读写：追加/删除行）。."""

    def __init__(self, parent: object | None = None) -> None:
        """初始化空模型。."""
        super().__init__(parent)
        self._rules: list[CleanRule] = []

    def roleNames(self) -> dict[int, QByteArray]:
        """声明角色名映射。."""
        return {
            Qt.UserRole + 1: _ROLE_KIND,
            Qt.UserRole + 2: _ROLE_COLUMN,
            Qt.UserRole + 3: _ROLE_VALUE,
            Qt.UserRole + 4: _ROLE_REPLACEMENT,
            Qt.UserRole + 5: _ROLE_CASE_MODE,
            Qt.UserRole + 6: _ROLE_DISPLAY,
        }

    def rowCount(self, parent: QModelIndex = _NO_PARENT) -> int:
        """行数 = 规则数。."""
        return 0 if parent.isValid() else len(self._rules)

    def data(self, index: QModelIndex, role: int = Qt.DisplayRole) -> Any:
        """按角色返回规则字段。."""
        if not index.isValid() or not (0 <= index.row() < len(self._rules)):
            return None
        rule = self._rules[index.row()]
        values: dict[int, Any] = {
            1: rule.kind.value,
            2: rule.column,
            3: rule.value,
            4: rule.replacement,
            5: rule.case_mode.value,
            6: rule.describe(),
        }
        return values.get(role - Qt.UserRole)

    def append_rule(self, rule: CleanRule) -> None:
        """尾部追加规则并通知视图。."""
        row = len(self._rules)
        self.beginInsertRows(_NO_PARENT, row, row)
        self._rules.append(rule)
        self.endInsertRows()

    def remove_row(self, row: int) -> None:
        """删除指定行（越界静默忽略）。."""
        if not (0 <= row < len(self._rules)):
            return
        self.beginRemoveRows(_NO_PARENT, row, row)
        del self._rules[row]
        self.endRemoveRows()

    def clear(self) -> None:
        """清空全部规则。."""
        self.beginResetModel()
        self._rules = []
        self.endResetModel()

    def rule_at(self, row: int) -> CleanRule | None:
        """按行号取规则（越界返回 None）。."""
        if 0 <= row < len(self._rules):
            return self._rules[row]
        return None

    def rules(self) -> list[CleanRule]:
        """全部规则列表（内部只读访问）。."""
        return list(self._rules)


class StringListModel(QAbstractListModel):
    """通用字符串列表模型（列名选择用）。."""

    def __init__(self, parent: object | None = None) -> None:
        """初始化空模型。."""
        super().__init__(parent)
        self._items: list[str] = []

    def roleNames(self) -> dict[int, QByteArray]:
        """只暴露 text 角色。."""
        return {Qt.UserRole + 1: _ROLE_TEXT}

    def rowCount(self, parent: QModelIndex = _NO_PARENT) -> int:
        """行数 = 条目数。."""
        return 0 if parent.isValid() else len(self._items)

    def data(self, index: QModelIndex, role: int = Qt.DisplayRole) -> Any:
        """返回行文本。."""
        if not index.isValid() or not (0 <= index.row() < len(self._items)):
            return None
        if role == Qt.UserRole + 1:
            return self._items[index.row()]
        return None

    def reload(self, items: list[str]) -> None:
        """整体替换数据并通知视图。."""
        self.beginResetModel()
        self._items = list(items)
        self.endResetModel()

    def item_at(self, row: int) -> str | None:
        """按行号取条目（越界返回 None）。."""
        if 0 <= row < len(self._items):
            return self._items[row]
        return None


class CleanPreviewModel(QAbstractTableModel):
    """清洗预览表格模型（前 N 行，列头为原列名）。."""

    def __init__(self, parent: object | None = None) -> None:
        """初始化空模型。."""
        super().__init__(parent)
        self._columns: list[str] = []
        self._rows: list[tuple[object, ...]] = []

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
