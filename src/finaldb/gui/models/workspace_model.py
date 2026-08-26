"""工作区列表模型：WorkspaceMeta → QAbstractListModel。."""

from __future__ import annotations

import time
from typing import Any

from PySide2.QtCore import QAbstractListModel, QByteArray, QModelIndex, Qt

from finaldb.core.workspace import WorkspaceMeta

__all__ = ["WorkspaceListModel"]

# 角色名 → QML 侧通过 model.name / model.tables 访问
_ROLE_NAME = QByteArray(b"name")
_ROLE_TABLES = QByteArray(b"tableCount")
_ROLE_ROWS = QByteArray(b"totalRows")
_ROLE_UPDATED = QByteArray(b"updatedAt")
_ROLE_PATH = QByteArray(b"path")

# QModelIndex 为不可值类型，作默认参数的模块级单例（B008 规避）
_NO_PARENT = QModelIndex()


class WorkspaceListModel(QAbstractListModel):
    """工作区概要列表模型（供首页 ListView 使用）。."""

    def __init__(self, parent: object | None = None) -> None:
        """初始化空模型。."""
        super().__init__(parent)
        self._metas: list[WorkspaceMeta] = []

    def roleNames(self) -> dict[int, QByteArray]:
        """声明角色名映射。."""
        return {
            Qt.UserRole + 1: _ROLE_NAME,
            Qt.UserRole + 2: _ROLE_TABLES,
            Qt.UserRole + 3: _ROLE_ROWS,
            Qt.UserRole + 4: _ROLE_UPDATED,
            Qt.UserRole + 5: _ROLE_PATH,
        }

    def rowCount(self, parent: QModelIndex = _NO_PARENT) -> int:
        """行数 = 工作区数量。."""
        return 0 if parent.isValid() else len(self._metas)

    def data(self, index: QModelIndex, role: int = Qt.DisplayRole) -> Any:
        """按角色返回工作区概要字段。."""
        if not index.isValid() or not (0 <= index.row() < len(self._metas)):
            return None
        meta = self._metas[index.row()]
        key = role - Qt.UserRole
        value: object = None
        if key == 1:
            value = meta.name
        elif key == 2:
            value = meta.table_count
        elif key == 3:
            value = meta.total_rows
        elif key == 4:
            updated = meta.updated_at
            value = "—" if updated <= 0 else time.strftime("%Y-%m-%d %H:%M", time.localtime(updated))
        elif key == 5:
            value = str(meta.path)
        return value

    def reload(self, metas: list[WorkspaceMeta]) -> None:
        """整体替换数据并通知视图。."""
        self.beginResetModel()
        self._metas = list(metas)
        self.endResetModel()

    def meta_at(self, row: int) -> WorkspaceMeta | None:
        """按行号取概要（越界返回 None）。."""
        if 0 <= row < len(self._metas):
            return self._metas[row]
        return None

    def clear(self) -> None:
        """清空模型。."""
        self.reload([])
