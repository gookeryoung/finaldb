"""WorkspaceManager 工作区生命周期测试。."""

from __future__ import annotations

from pathlib import Path

import pytest

from finaldb.core.exceptions import WorkspaceError
from finaldb.core.workspace import Workspace, WorkspaceManager, sanitize_workspace_name


@pytest.fixture()
def manager(tmp_path: Path) -> WorkspaceManager:
    """使用临时根目录的管理器。."""
    return WorkspaceManager(root=tmp_path / "workspaces")


def test_create_initializes_workspace(manager: WorkspaceManager, tmp_path: Path) -> None:
    """创建工作区应生成标记文件与空数据库。."""
    ws = manager.create("demo")
    assert ws.name == "demo"
    assert ws.db_path.is_file()
    assert (ws.path / "finaldb.json").is_file()
    assert ws.path.parent == manager.root


def test_create_sanitizes_name(manager: WorkspaceManager) -> None:
    """非法字符名称应被清洗为目录安全名。."""
    ws = manager.create("我的 数据 1")
    assert ws.name == "1"
    assert (manager.root / "1").is_dir()


def test_create_duplicate_raises(manager: WorkspaceManager) -> None:
    """同名工作区重复创建应报错。."""
    manager.create("demo")
    with pytest.raises(WorkspaceError, match="已存在"):
        manager.create("demo")


def test_create_empty_name_raises(manager: WorkspaceManager) -> None:
    """清洗后为空的名称应报错。."""
    with pytest.raises(WorkspaceError, match="无效"):
        manager.create("中文!!")


def test_list_empty_when_root_missing(manager: WorkspaceManager) -> None:
    """根目录不存在时列举返回空列表。."""
    assert manager.list() == []


def test_list_orders_by_recent_update(manager: WorkspaceManager, tmp_path: Path) -> None:
    """列举按数据库更新时间倒序，且统计表数与行数。."""
    import os
    import sqlite3

    old = manager.create("old")
    new = manager.create("new")
    conn = sqlite3.connect(str(new.db_path))
    conn.execute("CREATE TABLE t (a INTEGER)")
    conn.execute("INSERT INTO t VALUES (1), (2)")
    conn.commit()
    conn.close()
    # 显式让 new 的 mtime 晚于 old
    os.utime(old.db_path, (0, 0))
    metas = manager.list()
    assert [m.name for m in metas] == ["new", "old"]
    assert metas[0].table_count == 1
    assert metas[0].total_rows == 2
    assert metas[1].table_count == 0


def test_open_validates_marker(tmp_path: Path) -> None:
    """无标记文件的目录不能作为工作区打开。."""
    with pytest.raises(WorkspaceError, match="有效的工作区"):
        Workspace(tmp_path)


def test_meta_reports_stats(manager: WorkspaceManager) -> None:
    """meta 统计表数/行数/更新时间。."""
    import sqlite3

    ws = manager.create("demo")
    conn = sqlite3.connect(str(ws.db_path))
    conn.execute("CREATE TABLE a (x TEXT)")
    conn.commit()
    conn.close()
    meta = ws.meta()
    assert meta.name == "demo"
    assert meta.table_count == 1
    assert meta.total_rows == 0
    assert meta.updated_at > 0


def test_delete_removes_directory(manager: WorkspaceManager) -> None:
    """删除工作区应移除整个目录。."""
    ws = manager.create("demo")
    manager.delete(ws.path)
    assert not ws.path.exists()
    assert manager.list() == []


def test_delete_rejects_non_workspace(manager: WorkspaceManager, tmp_path: Path) -> None:
    """无标记文件的目录拒绝删除（防误删）。."""
    other = tmp_path / "plain"
    other.mkdir()
    with pytest.raises(WorkspaceError, match="拒绝删除"):
        manager.delete(other)


def test_sanitize_name_variants() -> None:
    """名称清洗的典型用例。."""
    assert sanitize_workspace_name("hello world") == "hello_world"
    assert sanitize_workspace_name("  spaced  ") == "spaced"
    assert sanitize_workspace_name("a/b\\c:d") == "a_b_c_d"
    assert sanitize_workspace_name("中文") == ""


def test_open_corrupt_marker_raises(tmp_path: Path) -> None:
    """标记文件损坏时应报错而非崩溃。."""
    ws_dir = tmp_path / "broken"
    ws_dir.mkdir()
    (ws_dir / "finaldb.json").write_text("{ not json", "utf-8")
    with pytest.raises(WorkspaceError, match="损坏"):
        Workspace(ws_dir)
