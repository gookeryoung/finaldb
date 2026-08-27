"""版本控制测试：快照提交与变更检测（导入自动快照底层能力）。."""

from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from pathlib import Path

import pytest

from finaldb.core.exceptions import VersionError
from finaldb.core.versioning import commit_snapshot, has_changes


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


def test_commit_returns_info(ws: Path) -> None:
    """提交快照返回摘要（完整 id / 短 id / 说明 / 时间戳）。."""
    info = commit_snapshot(ws, "首次导入")
    assert info.message == "首次导入"
    assert len(info.commit_id) == 40
    assert info.short_id == info.commit_id[:7]
    assert info.timestamp > 0
    # 第二次提交时间不早于第一次
    _write_rows(ws, [("甲", 30), ("乙", 25)])
    second = commit_snapshot(ws, "补充数据")
    assert second.timestamp >= info.timestamp


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


def test_has_changes_without_db(tmp_path: Path) -> None:
    """无数据库文件时视为无变化（无可提交内容）。."""
    empty = tmp_path / "empty"
    empty.mkdir()
    assert has_changes(empty) is False
