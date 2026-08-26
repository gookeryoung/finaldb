"""工作区生命周期管理：创建 / 打开 / 列举 / 删除。

一个工作区 = 一个目录，包含：

- ``data.db``：SQLite 运行库
- ``finaldb.json``：工作区标记文件（名称、版本、创建时间）

工作区根目录默认 ``~/.finaldb/workspaces``，可注入自定义路径用于测试。
"""

from __future__ import annotations

import json
import re
import shutil
import time
from pathlib import Path
from typing import Any

import sqlite3

from finaldb.core.exceptions import WorkspaceError
from finaldb.core.storage.database import connect, table_infos

__all__ = ["Workspace", "WorkspaceManager", "WorkspaceMeta"]

# 工作区标记文件名
_MARKER_FILE = "finaldb.json"
# 工作区标记格式版本
_MARKER_VERSION = 1


class WorkspaceMeta:
    """工作区概要信息（列表展示用，不持有连接）。."""

    __slots__ = ("name", "path", "table_count", "total_rows", "updated_at")

    def __init__(
        self,
        name: str,
        path: Path,
        table_count: int = 0,
        total_rows: int = 0,
        updated_at: float = 0.0,
    ) -> None:
        """初始化工作区概要。

        :param name: 工作区名称
        :param path: 工作区目录
        :param table_count: 表数量
        :param total_rows: 全部表行数总和
        :param updated_at: 数据库文件最后修改时间戳
        """
        self.name = name
        self.path = path
        self.table_count = table_count
        self.total_rows = total_rows
        self.updated_at = updated_at

    def __repr__(self) -> str:
        """可读表示（含关键字段）。."""
        return (
            f"WorkspaceMeta(name={self.name!r}, path={str(self.path)!r}, "
            f"table_count={self.table_count}, total_rows={self.total_rows})"
        )


class Workspace:
    """打开状态的工作区：目录 + 数据库路径 + 便捷访问。."""

    __slots__ = ("_path", "_name")

    def __init__(self, path: Path) -> None:
        """打开工作区（校验标记文件存在）。

        :param path: 工作区目录
        :raises WorkspaceError: 目录不存在或缺少标记文件
        """
        marker = path / _MARKER_FILE
        if not marker.is_file():
            raise WorkspaceError(f"不是有效的工作区目录: {path}")
        self._path = path
        self._name = _read_marker(path)["name"]

    @property
    def path(self) -> Path:
        """工作区目录。."""
        return self._path

    @property
    def name(self) -> str:
        """工作区名称。."""
        return self._name

    @property
    def db_path(self) -> Path:
        """SQLite 数据库文件路径。."""
        return self._path / "data.db"

    def connect(self) -> sqlite3.Connection:
        """打开数据库连接（调用方负责关闭）。."""
        return connect(self.db_path)

    def meta(self) -> WorkspaceMeta:
        """统计当前工作区概要（表数/总行数/更新时间）。."""
        conn = self.connect()
        try:
            infos = table_infos(conn)
        finally:
            conn.close()
        return WorkspaceMeta(
            name=self._name,
            path=self._path,
            table_count=len(infos),
            total_rows=sum(t.row_count for t in infos),
            updated_at=self.db_path.stat().st_mtime if self.db_path.exists() else 0.0,
        )

    def __repr__(self) -> str:
        """可读表示（含关键字段）。."""
        return f"Workspace(name={self._name!r}, path={str(self._path)!r})"


class WorkspaceManager:
    """工作区管理器：在工作区根目录下创建/列举/删除工作区。."""

    __slots__ = ("_root",)

    def __init__(self, root: Path | None = None) -> None:
        """初始化管理器。

        :param root: 工作区根目录，默认 ``~/.finaldb/workspaces``
        """
        self._root = root if root is not None else Path.home() / ".finaldb" / "workspaces"

    @property
    def root(self) -> Path:
        """工作区根目录。."""
        return self._root

    def create(self, name: str) -> Workspace:
        """创建新工作区（目录 + 标记 + 空数据库）。

        :param name: 工作区名称（自动清洗为目录安全名）
        :return: 打开的新工作区
        :raises WorkspaceError: 名称清洗后为空或目录已存在
        """
        safe = sanitize_workspace_name(name)
        if not safe:
            raise WorkspaceError(f"无效的工作区名称: {name!r}")
        path = self._root / safe
        if path.exists():
            raise WorkspaceError(f"工作区已存在: {safe}")
        self._root.mkdir(parents=True, exist_ok=True)
        path.mkdir()
        _write_marker(path, safe)
        # 建库文件：connect 隐式创建
        conn = connect(path / "data.db")
        conn.close()
        return Workspace(path)

    def open(self, path: Path) -> Workspace:
        """按目录打开既有工作区。

        :param path: 工作区目录
        :raises WorkspaceError: 标记文件缺失或非法
        """
        return Workspace(path)

    def list(self) -> "list[WorkspaceMeta]":
        """列举根目录下全部工作区（按更新时间倒序）。."""
        if not self._root.is_dir():
            return []
        metas = []
        for child in sorted(self._root.iterdir()):
            if child.is_dir() and (child / _MARKER_FILE).is_file():
                ws = Workspace(child)
                metas.append(ws.meta())
        metas.sort(key=lambda m: m.updated_at, reverse=True)
        return metas

    def delete(self, path: Path) -> None:
        """删除工作区目录（含数据库，不可恢复）。

        :param path: 工作区目录
        :raises WorkspaceError: 目录不是有效工作区（防误删任意目录）
        """
        if not (path / _MARKER_FILE).is_file():
            raise WorkspaceError(f"不是有效的工作区目录，拒绝删除: {path}")
        shutil.rmtree(path)


def sanitize_workspace_name(name: str) -> str:
    """清洗工作区名称为目录安全名（字母数字下划线连字符）。

    非法字符替换为下划线；中文等被替换后若全空则返回空串。

    :param name: 原始名称
    :return: 清洗后的名称（可能为空串）
    """
    cleaned = re.sub(r"[^A-Za-z0-9_-]+", "_", name.strip())
    return cleaned.strip("_")


def _read_marker(path: Path) -> dict[str, Any]:
    """读取工作区标记文件内容。

    :param path: 工作区目录
    :return: 标记内容字典（至少含 name）
    :raises WorkspaceError: 标记文件损坏或缺少 name 字段
    """
    marker = path / _MARKER_FILE
    try:
        data = json.loads(marker.read_text("utf-8"))
    except (OSError, ValueError) as exc:
        raise WorkspaceError(f"工作区标记文件损坏: {marker}") from exc
    if not isinstance(data, dict) or "name" not in data:
        raise WorkspaceError(f"工作区标记文件缺少 name 字段: {marker}")
    return data


def _write_marker(path: Path, name: str) -> None:
    """写入工作区标记文件。

    :param path: 工作区目录
    :param name: 工作区名称
    """
    payload = {"name": name, "version": _MARKER_VERSION, "created_at": time.time()}
    (path / _MARKER_FILE).write_text(json.dumps(payload, ensure_ascii=False, indent=2), "utf-8")
