"""core 层门面：仅做 re-export，不含业务实现。."""

from __future__ import annotations

from finaldb.core.cleaning import CleanReport, CleanRule, CleanSummary, RuleKind, clean_table
from finaldb.core.exceptions import (
    CleanError,
    FinaldbError,
    MergeError,
    TableExistsError,
    UnsupportedFormatError,
    VersionError,
    WorkspaceError,
)
from finaldb.core.importers import import_file, import_into_workspace
from finaldb.core.merge import JoinSpec, MergeJob, MergeSummary, dedup_table, join_tables, union_tables
from finaldb.core.stats import ColumnStat, WorkspaceOverview, column_stats, workspace_overview
from finaldb.core.storage.database import TableInfo, connect
from finaldb.core.versioning import (
    SnapshotInfo,
    commit_snapshot,
    has_changes,
    list_snapshots,
    restore_snapshot,
    snapshot_diff,
)
from finaldb.core.workspace import Workspace, WorkspaceManager, WorkspaceMeta

__all__ = [
    "CleanError",
    "CleanReport",
    "CleanRule",
    "CleanSummary",
    "ColumnStat",
    "FinaldbError",
    "JoinSpec",
    "MergeError",
    "MergeJob",
    "MergeSummary",
    "RuleKind",
    "SnapshotInfo",
    "TableExistsError",
    "TableInfo",
    "UnsupportedFormatError",
    "VersionError",
    "Workspace",
    "WorkspaceError",
    "WorkspaceManager",
    "WorkspaceMeta",
    "WorkspaceOverview",
    "clean_table",
    "column_stats",
    "commit_snapshot",
    "connect",
    "dedup_table",
    "has_changes",
    "import_file",
    "import_into_workspace",
    "join_tables",
    "list_snapshots",
    "restore_snapshot",
    "snapshot_diff",
    "union_tables",
    "workspace_overview",
]
