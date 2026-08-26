"""快照列表模型：QML 历史页的快照条目展示。."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from PySide2.QtCore import (
    QAbstractListModel,
    QByteArray,
    QModelIndex,
    Qt,
)

from finaldb.core.versioning import SnapshotInfo

__all__ = ["SnapshotListModel"]

_NO_PARENT = QModelIndex()

# 角色名（QML delegate 通过 model.角色名 取值）
_ROLE_SHORT_ID = QByteArray(b"shortId")
_ROLE_MESSAGE = QByteArray(b"message")
_ROLE_TIME = QByteArray(b"time")
_ROLE_DISPLAY = QByteArray(b"display")


def _format_time(timestamp: int) -> str:
    """Unix 秒转本地可读时间。."""
    return datetime.fromtimestamp(timestamp).strftime("%Y-%m-%d %H:%M:%S")


class SnapshotListModel(QAbstractListModel):
    """快照列表模型（display = 短 id + 说明 + 时间单行摘要）。."""

    def __init__(self, parent: object | None = None) -> None:
        """初始化空列表。."""
        super().__init__(parent)
        self._snapshots: list[SnapshotInfo] = []

    def roleNames(self) -> dict[int, QByteArray]:
        """声明 QML 角色名。."""
        return {
            Qt.UserRole + 1: _ROLE_SHORT_ID,
            Qt.UserRole + 2: _ROLE_MESSAGE,
            Qt.UserRole + 3: _ROLE_TIME,
            Qt.UserRole + 4: _ROLE_DISPLAY,
        }

    def rowCount(self, parent: QModelIndex = _NO_PARENT) -> int:
        """条目数（扁平列表无子级）。."""
        return 0 if parent.isValid() else len(self._snapshots)

    def data(self, index: QModelIndex, role: int = Qt.DisplayRole) -> Any:
        """按角色返回条目数据（越界/未知角色返回 None）。."""
        if not index.isValid() or not (0 <= index.row() < len(self._snapshots)):
            return None
        snap = self._snapshots[index.row()]
        role_name = self.roleNames().get(role)
        if role_name == _ROLE_SHORT_ID:
            return snap.short_id
        if role_name == _ROLE_MESSAGE:
            return snap.message
        if role_name == _ROLE_TIME:
            return _format_time(snap.timestamp)
        if role_name == _ROLE_DISPLAY:
            return f"{snap.short_id}  {_format_time(snap.timestamp)}  {snap.message}"
        return None

    def reload(self, snapshots: list[SnapshotInfo]) -> None:
        """整表替换并刷新。."""
        self.beginResetModel()
        self._snapshots = list(snapshots)
        self.endResetModel()

    def snapshot_at(self, row: int) -> SnapshotInfo | None:
        """按行号取快照（越界返回 None）。."""
        if 0 <= row < len(self._snapshots):
            return self._snapshots[row]
        return None
