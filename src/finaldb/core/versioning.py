"""版本控制：基于 dulwich 的快照级提交与变更检测。

快照语义：每次提交把工作区的 ``data.db`` 整体存为一个 git blob；
不做行级 merge。当前仅保留提交与变更检测（导入自动快照），
历史列表/对比/回滚等 GUI 入口已随版本页移除。
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import cast

from dulwich import porcelain
from dulwich.errors import NotGitRepository
from dulwich.objects import Blob, Commit, Tree
from dulwich.repo import Repo

from finaldb.core.exceptions import VersionError

__all__ = [
    "SnapshotInfo",
    "commit_snapshot",
    "has_changes",
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
    """当前数据库与最新快照是否存在差异（无仓库时视为有变化）。"""
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


# ----------------------------- 内部 -----------------------------


def _open_or_init(ws_path: Path) -> Repo:
    """打开工作区内嵌 git 仓库，不存在则初始化。"""
    try:
        return Repo(str(ws_path))
    except NotGitRepository:
        return porcelain.init(str(ws_path))


def _head_sha(repo: Repo) -> bytes | None:
    """当前分支头提交 id（空仓库返回 None）。"""
    try:
        return repo.head()
    except (KeyError, IndexError):
        return None


def _db_blob(repo: Repo, sha: bytes) -> bytes:
    """读取指定提交里 data.db 的 blob 内容（缺失报错）。"""
    commit = cast(Commit, repo[sha])
    tree = cast(Tree, repo[commit.tree])
    try:
        _mode, blob_sha = tree.lookup_path(repo.object_store.__getitem__, _DB_ENTRY)
    except KeyError as exc:
        raise VersionError(f"快照 {sha.decode('ascii', 'ignore')} 不含数据库") from exc
    return cast(Blob, repo[blob_sha]).data


def _info_of(commit: Commit) -> SnapshotInfo:
    """把 dulwich Commit 转为快照摘要。"""
    commit_id = commit.id.decode("ascii")
    message = commit.message.decode("utf-8", "replace").strip()
    return SnapshotInfo(
        commit_id=commit_id,
        short_id=commit_id[:_SHORT_LEN],
        message=message.splitlines()[0] if message else "（无说明）",
        timestamp=commit.commit_time,
    )
