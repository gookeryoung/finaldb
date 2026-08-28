"""可编辑表格模型：rowid 定位的双向绑定（显示 + 单元格编辑）。."""

from __future__ import annotations

from typing import Any

from PySide2.QtCore import QAbstractTableModel, QModelIndex, Qt

__all__ = ["EditableTableModel"]

# QModelIndex 为不可值类型，作默认参数的模块级单例（B008 规避）
_NO_PARENT = QModelIndex()


class EditableTableModel(QAbstractTableModel):
    """表数据编辑模型：rows 为 [(rowid, 行值元组), ...]。

    单元格编辑（setData）经回调委托给控制器落库，成功后更新本地缓存；
    行列结构变化由控制器整页重载（reset_data）。
    """

    def __init__(self, parent: object | None = None) -> None:
        """初始化空模型。."""
        super().__init__(parent)
        self._columns: list[str] = []
        self._rows: list[tuple[int, tuple[object, ...]]] = []
        self._set_cell_callback: Any = None
        self._key_column = ""

    def set_cell_callback(self, callback: Any) -> None:
        """注册单元格落库回调 callback(rowid, column, text) -> bool。

        Args:
            callback: 返回 True 表示落库成功（模型更新缓存）
        """
        self._set_cell_callback = callback

    def set_key_column(self, column: str) -> None:
        """设置键列（列头追加「·键」标识；空串清除）。."""
        self._key_column = column
        if self._columns:
            self.headerDataChanged.emit(Qt.Horizontal, 0, len(self._columns) - 1)

    # ----------------------------- Qt 模型协议 -----------------------------

    def rowCount(self, parent: QModelIndex = _NO_PARENT) -> int:
        """行数。."""
        return 0 if parent.isValid() else len(self._rows)

    def columnCount(self, parent: QModelIndex = _NO_PARENT) -> int:
        """列数。."""
        return 0 if parent.isValid() else len(self._columns)

    def flags(self, index: QModelIndex) -> Qt.ItemFlags:
        """全部单元格可编辑。."""
        base = Qt.ItemIsEnabled | Qt.ItemIsSelectable
        return base | Qt.ItemIsEditable if index.isValid() else base

    def data(self, index: QModelIndex, role: int = Qt.DisplayRole) -> Any:
        """返回单元格显示文本（None 显示为空串）。."""
        if not index.isValid() or role not in (Qt.DisplayRole, Qt.EditRole):
            return None
        if not (0 <= index.row() < len(self._rows)):
            return None
        row = self._rows[index.row()][1]
        col = index.column()
        if not (0 <= col < len(row)):
            return None
        value = row[col]
        return "" if value is None else str(value)

    def setData(self, index: QModelIndex, value: Any, role: int = Qt.EditRole) -> bool:
        """单元格编辑：委托回调落库，成功后更新缓存。."""
        if not index.isValid() or role != Qt.EditRole:
            return False
        if self._set_cell_callback is None:
            return False
        if not (0 <= index.row() < len(self._rows)):
            return False
        rowid, values = self._rows[index.row()]
        col = index.column()
        if not (0 <= col < len(self._columns)):
            return False
        ok = bool(self._set_cell_callback(rowid, self._columns[col], str(value)))
        if ok:
            new_values = (*values[:col], value, *values[col + 1 :])
            self._rows[index.row()] = (rowid, new_values)
            self.dataChanged.emit(index, index)
        return ok

    def headerData(self, section: int, orientation: Qt.Orientation, role: int = Qt.DisplayRole) -> Any:
        """列头返回列名（键列追加「·键」标识）。."""
        if role == Qt.DisplayRole and orientation == Qt.Horizontal and 0 <= section < len(self._columns):
            name = self._columns[section]
            return f"{name} ·键" if name == self._key_column else name
        if (
            role == Qt.ToolTipRole
            and orientation == Qt.Horizontal
            and 0 <= section < len(self._columns)
            and self._columns[section] == self._key_column
        ):
            return f"{self._key_column} 为自增键列：追加行时自动填入下一序号"
        return None

    # ----------------------------- 数据装载 -----------------------------

    def reset_data(self, columns: list[str], rows: list[tuple[int, tuple[object, ...]]]) -> None:
        """整体替换数据并通知视图。."""
        self.beginResetModel()
        self._columns = list(columns)
        self._rows = list(rows)
        self.endResetModel()

    def column_names(self) -> list[str]:
        """当前列名列表（模型数据源，不含键标识）。."""
        return list(self._columns)

    def rowid_at(self, row: int) -> int | None:
        """按视图行号取 rowid（越界返回 None）。."""
        if 0 <= row < len(self._rows):
            return self._rows[row][0]
        return None

    def rowids_of(self, rows: list[int]) -> list[int]:
        """按视图行号列表批量取 rowid（跳过越界）。."""
        return [rid for rid in (self.rowid_at(r) for r in rows) if rid is not None]
