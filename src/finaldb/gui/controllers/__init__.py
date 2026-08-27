"""controllers 门面：仅做 re-export。."""

from __future__ import annotations

from finaldb.gui.controllers.about_controller import AboutController
from finaldb.gui.controllers.clean_controller import CleanController
from finaldb.gui.controllers.editing_controller import EditingController
from finaldb.gui.controllers.merge_controller import MergeController
from finaldb.gui.controllers.stats_controller import StatsController
from finaldb.gui.controllers.workspace_controller import WorkspaceController

__all__ = [
    "AboutController",
    "CleanController",
    "EditingController",
    "MergeController",
    "StatsController",
    "WorkspaceController",
]
