"""core 层门面：仅做 re-export，不含业务实现。."""

from __future__ import annotations

from finaldb.core.cleaning import CleanReport, CleanRule, CleanSummary, RuleKind, clean_table
from finaldb.core.exceptions import (
    CleanError,
    FinaldbError,
    MergeError,
    TableExistsError,
    UnsupportedFormatError,
    WorkspaceError,
)
from finaldb.core.importers import import_file, import_into_workspace
from finaldb.core.merge import JoinSpec, MergeJob, MergeSummary, dedup_table, join_tables, union_tables
from finaldb.core.storage.database import TableInfo, connect
from finaldb.core.workspace import Workspace, WorkspaceManager, WorkspaceMeta

__all__ = [
    "CleanError",
    "CleanReport",
    "CleanRule",
    "CleanSummary",
    "FinaldbError",
    "JoinSpec",
    "MergeError",
    "MergeJob",
    "MergeSummary",
    "RuleKind",
    "TableExistsError",
    "TableInfo",
    "UnsupportedFormatError",
    "Workspace",
    "WorkspaceError",
    "WorkspaceManager",
    "WorkspaceMeta",
    "clean_table",
    "connect",
    "dedup_table",
    "import_file",
    "import_into_workspace",
    "join_tables",
    "union_tables",
]
