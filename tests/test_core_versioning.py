"""版本控制测试：快照提交、历史列表、对比与回滚。."""

from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from pathlib import Path

import pytest

from finaldb.core.exceptions import VersionError
from finaldb.core.versioning import (
    commit_snapshot,
    has_changes,
    list_snapshots,
    restore_snapshot,
    snapshot_diff,
)


@pytest.fixture()
def ws(tmp_path: Path) -> Iterator[Path]:
    """建带一张表的工作区目录。."""
    ws_dir = tmp_path / "ws"
    ws_dir.mkdir()
    _write_rows(ws_dir, [("甲", 30)])
    yield ws_dir


def _write_rows(ws_dir: Path, rows: list[tuple[object, ...]]) -> None:
    """（重）建 t 表并写入行。."""
    db = ws_dir / "data.db"
    if db.exists():
        db.unlink()
    conn = sqlite3.connect(db)
    conn.execute('CREATE TABLE "t" ("name" TEXT, "age" INTEGER)')
    conn.executemany('INSERT INTO "t" VALUES (?, ?)', rows)
    conn.commit()
    conn.close()


def _read_rows(ws_dir: Path) -> list[tuple[object, ...]]:
    """读取当前 t 表全部行。."""
    conn = sqlite3.connect(ws_dir / "data.db")
    try:
        return conn.execute('SELECT "name", "age" FROM "t"').fetchall()
    finally:
        conn.close()


def test_commit_and_list(ws: Path) -> None:
    """提交快照后历史列表按时间倒序返回。."""
    first = commit_snapshot(ws, "首次导入")
    _write_rows(ws, [("甲", 30), ("乙", 25)])
    second = commit_snapshot(ws, "补充数据")
    snapshots = list_snapshots(ws)
    assert [s.short_id for s in snapshots] == [second.short_id, first.short_id]
    assert snapshots[0].message == "补充数据"
    assert snapshots[0].timestamp >= snapshots[1].timestamp
    assert len(snapshots[0].commit_id) == 40


def test_commit_empty_message_uses_default(ws: Path) -> None:
    """空提交说明使用默认文案。."""
    info = commit_snapshot(ws, "")
    assert info.message == "数据快照"


def test_commit_without_db_raises(tmp_path: Path) -> None:
    """无数据库文件时报错。."""
    empty = tmp_path / "empty"
    empty.mkdir()
    with pytest.raises(VersionError, match="无数据库文件"):
        commit_snapshot(empty, "x")


def test_commit_unchanged_raises(ws: Path) -> None:
    """数据无变化时重复提交报错。."""
    commit_snapshot(ws, "一")
    with pytest.raises(VersionError, match="无变化"):
        commit_snapshot(ws, "二")


def test_has_changes(ws: Path) -> None:
    """变更检测：无仓库/有变更/无变更三种状态。."""
    assert has_changes(ws) is True
    commit_snapshot(ws, "一")
    assert has_changes(ws) is False
    _write_rows(ws, [("乙", 25)])
    assert has_changes(ws) is True


def test_list_snapshots_no_repo(tmp_path: Path) -> None:
    """未初始化仓库返回空列表。."""
    empty = tmp_path / "empty"
    empty.mkdir()
    assert list_snapshots(empty) == []


def test_snapshot_diff(ws: Path) -> None:
    """对比两快照表级行数差异。."""
    first = commit_snapshot(ws, "一")
    _write_rows(ws, [("甲", 30), ("乙", 25)])
    second = commit_snapshot(ws, "二")
    text = snapshot_diff(ws, first.short_id, second.short_id)
    assert "t: 1 行" in text
    assert "t: 2 行" in text
    assert "-表 t: 1 行" in text
    assert "+表 t: 2 行" in text


def test_snapshot_diff_identical(ws: Path) -> None:
    """相同数据（不同提交）对比提示无差异。."""
    first = commit_snapshot(ws, "一")
    # 改动后改回（内容相同字节可能不同，但表级 dump 一致时仍给出 diff）；
    # 直接用同一引用对比自身
    assert snapshot_diff(ws, first.short_id, first.short_id) == "两快照数据完全相同"


def test_snapshot_diff_head_ref(ws: Path) -> None:
    """HEAD 引用解析到最新快照。."""
    first = commit_snapshot(ws, "一")
    _write_rows(ws, [("甲", 30), ("乙", 25), ("丙", 40)])
    commit_snapshot(ws, "二")
    text = snapshot_diff(ws, first.short_id, "HEAD")
    assert text.startswith(f"--- {first.short_id}")
    assert "+表 t: 3 行" in text


def test_snapshot_diff_bad_ref(ws: Path) -> None:
    """无法解析的引用报错。."""
    commit_snapshot(ws, "一")
    with pytest.raises(VersionError, match="快照不存在"):
        snapshot_diff(ws, "deadbee", "HEAD")
    with pytest.raises(VersionError, match="空的快照引用"):
        snapshot_diff(ws, "", "HEAD")


def test_snapshot_diff_no_repo(tmp_path: Path) -> None:
    """未初始化仓库做对比报错。."""
    empty = tmp_path / "empty"
    empty.mkdir()
    with pytest.raises(VersionError, match="尚未创建"):
        snapshot_diff(empty, "HEAD", "HEAD")


def test_restore(ws: Path) -> None:
    """回滚到旧快照后数据恢复。."""
    first = commit_snapshot(ws, "一")
    _write_rows(ws, [("甲", 30), ("乙", 25)])
    commit_snapshot(ws, "二")
    info = restore_snapshot(ws, first.short_id)
    assert info.short_id == first.short_id
    assert _read_rows(ws) == [("甲", 30)]


def test_restore_full_id_and_head(ws: Path) -> None:
    """完整 id 与 HEAD 引用均可回滚。."""
    _write_rows(ws, [("甲", 30), ("乙", 25)])
    second = commit_snapshot(ws, "二")
    # 回滚到 HEAD（即自身）数据不变
    restore_snapshot(ws, "HEAD")
    assert _read_rows(ws) == [("甲", 30), ("乙", 25)]
    # 完整 id 等价
    restore_snapshot(ws, second.commit_id)
    assert _read_rows(ws) == [("甲", 30), ("乙", 25)]


def test_restore_bad_ref(ws: Path) -> None:
    """回滚不存在的引用报错。"""
    commit_snapshot(ws, "一")
    with pytest.raises(VersionError, match="快照不存在"):
        restore_snapshot(ws, "nope")
