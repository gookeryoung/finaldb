"""core 层门面：仅做 re-export，不含业务实现。."""

from __future__ import annotations

from finaldb.core.exceptions import (
    FinaldbError,
    TableExistsError,
    UnsupportedFormatError,
    WorkspaceError,
)
from finaldb.core.importers import import_file, import_into_workspace
from finaldb.core.storage.database import TableInfo, connect
from finaldb.core.workspace import Workspace, WorkspaceManager, WorkspaceMeta

__all__ = [
    "FinaldbError",
    "TableExistsError",
    "UnsupportedFormatError",
    "WorkspaceError",
    "Workspace",
    "WorkspaceManager",
    "WorkspaceMeta",
    "TableInfo",
    "connect",
    "import_file",
    "import_into_workspace",
]
