"""版本控制：基于 dulwich 的快照级提交/历史/对比/回滚。

快照语义：每次提交把工作区的 ``data.db`` 整体存为一个 git blob；
不做行级 merge，回滚即用历史 blob 覆盖当前数据库。
"""

from __future__ import annotations

import sqlite3
import tempfile
from dataclasses import dataclass
from difflib import unified_diff
from operator import attrgetter
from pathlib import Path
from typing import cast

from dulwich import porcelain
from dulwich.errors import NotGitRepository
from dulwich.objects import Blob, Commit, Tree
from dulwich.repo import Repo

from finaldb.core.exceptions import VersionError
from finaldb.core.storage.database import table_infos

__all__ = [
    "SnapshotInfo",
    "commit_snapshot",
    "has_changes",
    "list_snapshots",
    "restore_snapshot",
    "snapshot_diff",
]

# 仓库内跟踪的文件（仅数据库一个条目）
_DB_ENTRY = b"data.db"

# 固定作者（快照级工具提交，不区分用户）
_AUTHOR = b"finaldb <finaldb@local>"

# 短 id 长度
_SHORT_LEN = 7


@dataclass(frozen=True)
class SnapshotInfo:
    """快照摘要。

    :ivar commit_id: 完整提交 id（40 位 hex）
    :ivar short_id: 短 id（前 7 位）
    :ivar message: 提交说明
    :ivar timestamp: 提交时间（Unix 秒）
    """

    commit_id: str
    short_id: str
    message: str
    timestamp: int


def commit_snapshot(ws_path: Path, message: str) -> SnapshotInfo:
    """把当前 data.db 提交为快照。

    :param ws_path: 工作区目录
    :param message: 提交说明（空串用默认文案）
    :return: 新快照摘要
    :raises VersionError: 数据库缺失或较上一快照无变化
    """
    db_path = ws_path / "data.db"
    if not db_path.is_file():
        raise VersionError("工作区无数据库文件")
    repo = _open_or_init(ws_path)
    data = db_path.read_bytes()
    parent = _head_sha(repo)
    if parent is not None and _db_blob(repo, parent) == data:
        raise VersionError("数据较上一快照无变化")
    text = message.strip() or "数据快照"
    porcelain.add(repo, [str(db_path)])
    sha = porcelain.commit(repo, text.encode("utf-8"), author=_AUTHOR, committer=_AUTHOR)
    return _info_of(cast(Commit, repo[sha]))


def has_changes(ws_path: Path) -> bool:
    """当前数据库与最新快照是否存在差异（无仓库时视为有变化）。."""
    db_path = ws_path / "data.db"
    if not db_path.is_file():
        return False
    try:
        repo = Repo(str(ws_path))
    except NotGitRepository:
        return True
    parent = _head_sha(repo)
    if parent is None:
        return True
    return _db_blob(repo, parent) != db_path.read_bytes()


def list_snapshots(ws_path: Path) -> list[SnapshotInfo]:
    """按时间倒序列出全部快照（无仓库返回空列表）。."""
    try:
        repo = Repo(str(ws_path))
    except NotGitRepository:
        return []
    if _head_sha(repo) is None:
        return []
    snapshots = [_info_of(entry.commit) for entry in repo.get_walker()]
    snapshots.sort(key=attrgetter("timestamp"), reverse=True)
    return snapshots


def snapshot_diff(ws_path: Path, ref_old: str, ref_new: str) -> str:
    """对比两快照的表级差异（表集合、列与行数）。

    :param ws_path: 工作区目录
    :param ref_old: 旧快照引用（完整/短 id 或 ``HEAD``）
    :param ref_new: 新快照引用
    :return: 统一 diff 文本（相同则提示无差异）
    :raises VersionError: 引用无法解析
    """
    repo = _require_repo(ws_path)
    old_data = _db_blob(repo, _resolve(repo, ref_old))
    new_data = _db_blob(repo, _resolve(repo, ref_new))
    if old_data == new_data:
        return "两快照数据完全相同"
    old_lines = _dump_db(old_data)
    new_lines = _dump_db(new_data)
    diff = unified_diff(old_lines, new_lines, fromfile=ref_old, tofile=ref_new, lineterm="")
    return "\n".join(diff)


def restore_snapshot(ws_path: Path, ref: str) -> SnapshotInfo:
    """回滚：用指定快照的 data.db 覆盖当前数据库。

    :param ws_path: 工作区目录
    :param ref: 快照引用（完整/短 id 或 ``HEAD``）
    :return: 被恢复的快照摘要
    :raises VersionError: 引用无法解析
    """
    repo = _require_repo(ws_path)
    sha = _resolve(repo, ref)
    data = _db_blob(repo, sha)
    db_path = ws_path / "data.db"
    db_path.write_bytes(data)
    # 清理可能残留的 WAL/共享内存文件，避免旧缓存干扰回滚后的读取
    for suffix in ("-wal", "-shm"):
        side = ws_path / f"data.db{suffix}"
        if side.exists():
            side.unlink()
    return _info_of(cast(Commit, repo[sha]))


# ----------------------------- 内部 -----------------------------


def _open_or_init(ws_path: Path) -> Repo:
    """打开工作区内嵌 git 仓库，不存在则初始化。."""
    try:
        return Repo(str(ws_path))
    except NotGitRepository:
        return porcelain.init(str(ws_path))


def _require_repo(ws_path: Path) -> Repo:
    """打开仓库，未初始化抛 VersionError。."""
    try:
        return Repo(str(ws_path))
    except NotGitRepository as exc:
        raise VersionError("工作区尚未创建任何快照") from exc


def _head_sha(repo: Repo) -> bytes | None:
    """当前分支头提交 id（空仓库返回 None）。."""
    try:
        return repo.head()
    except (KeyError, IndexError):
        return None


def _resolve(repo: Repo, ref: str) -> bytes:
    """解析快照引用为完整提交 id。

    支持 ``HEAD``、完整 hex 与短 id 前缀匹配。
    """
    text = ref.strip()
    if not text:
        raise VersionError("空的快照引用")
    if text == "HEAD":
        sha = _head_sha(repo)
        if sha is None:
            raise VersionError("仓库尚无提交")
        return sha
    prefix = text.lower().encode("ascii")
    for entry in repo.get_walker():
        if entry.commit.id.lower().startswith(prefix):
            return entry.commit.id
    raise VersionError(f"快照不存在: {ref}")


def _db_blob(repo: Repo, sha: bytes) -> bytes:
    """读取指定提交里 data.db 的 blob 内容（缺失报错）。."""
    commit = cast(Commit, repo[sha])
    tree = cast(Tree, repo[commit.tree])
    try:
        _mode, blob_sha = tree.lookup_path(repo.object_store.__getitem__, _DB_ENTRY)
    except KeyError as exc:
        raise VersionError(f"快照 {sha.decode('ascii', 'ignore')} 不含数据库") from exc
    return cast(Blob, repo[blob_sha]).data


def _info_of(commit: Commit) -> SnapshotInfo:
    """把 dulwich Commit 转为快照摘要。."""
    commit_id = commit.id.decode("ascii")
    message = commit.message.decode("utf-8", "replace").strip()
    return SnapshotInfo(
        commit_id=commit_id,
        short_id=commit_id[:_SHORT_LEN],
        message=message.splitlines()[0] if message else "（无说明）",
        timestamp=commit.commit_time,
    )


def _dump_db(data: bytes) -> list[str]:
    """把数据库字节物化为临时文件并导出表级统计行（供 diff）。."""
    with tempfile.TemporaryDirectory() as tmp:
        db_file = Path(tmp) / "data.db"
        db_file.write_bytes(data)
        conn: sqlite3.Connection = sqlite3.connect(db_file)
        try:
            return [
                f"表 {info.name}: {info.row_count} 行 | 列: {', '.join(c.name for c in info.columns)}"
                for info in table_infos(conn)
            ]
        finally:
            conn.close()
