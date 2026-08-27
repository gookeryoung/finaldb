"""控制器装配表：构造页面控制器并按 key 组织（与入口解耦）。."""

from __future__ import annotations

from typing import Dict  # noqa: UP035  # 3.8 运行时下标兼容

from PySide2.QtCore import QObject

from finaldb.gui.controllers.about_controller import AboutController
from finaldb.gui.controllers.clean_controller import CleanController
from finaldb.gui.controllers.editing_controller import EditingController
from finaldb.gui.controllers.history_controller import HistoryController
from finaldb.gui.controllers.merge_controller import MergeController
from finaldb.gui.controllers.preview_controller import PreviewController
from finaldb.gui.controllers.stats_controller import StatsController
from finaldb.gui.controllers.workspace_controller import WorkspaceController

__all__ = ["Controllers", "create_controllers"]

# 控制器装配表：key -> 控制器实例（新页面在此追加即可）
# 注：模块级别名在 3.8 运行时求值，须用 typing.Dict 而非内置 dict 下标
Controllers = Dict[str, QObject]  # noqa: UP006  # 3.8 运行时下标兼容


def create_controllers() -> Controllers:
    """构造页面控制器装配表。

    Returns:
        key 到控制器实例的字典
    """
    return {
        "workspace": WorkspaceController(),
        "preview": PreviewController(),
        "clean": CleanController(),
        "merge": MergeController(),
        "editing": EditingController(),
        "history": HistoryController(),
        "stats": StatsController(),
        "about": AboutController(),
    }
