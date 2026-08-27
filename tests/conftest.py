"""GUI 测试共享 fixture：Qt 离屏环境与 Widgets 主窗口装配。."""

from __future__ import annotations

import os
import tempfile
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

# 必须在导入 PySide2 前设置：无头/CI 环境用离屏平台
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide2.QtWidgets import QApplication


@pytest.fixture(scope="session")
def qapp() -> Iterator[QApplication]:
    """会话级 QApplication 单例。."""
    app = QApplication.instance() or QApplication([])
    yield app
    app.processEvents()


@pytest.fixture()
def main_window(qapp: QApplication) -> Iterator[tuple[Any, ...]]:
    """装配完整 Widgets 应用（控制器 + 主窗口）。

    控制器使用临时工作区根目录，避免污染用户主目录。

    Yields:
        (主窗口, 主题管理器, 工作区控制器, 清洗控制器,
         合并控制器, 编辑控制器, 统计控制器, 关于控制器)
    """
    from finaldb.app import create_main_window
    from finaldb.gui.controllers.about_controller import AboutController
    from finaldb.gui.controllers.clean_controller import CleanController
    from finaldb.gui.controllers.editing_controller import EditingController
    from finaldb.gui.controllers.merge_controller import MergeController
    from finaldb.gui.controllers.stats_controller import StatsController
    from finaldb.gui.controllers.workspace_controller import WorkspaceController
    from finaldb.gui.theme import ThemeManager

    theme = ThemeManager()
    with tempfile.TemporaryDirectory() as tmp:
        workspace_ctrl = WorkspaceController(root=Path(tmp))
        clean_ctrl = CleanController()
        merge_ctrl = MergeController()
        editing_ctrl = EditingController()
        stats_ctrl = StatsController()
        about_ctrl = AboutController()
        controllers = {
            "workspace": workspace_ctrl,
            "clean": clean_ctrl,
            "merge": merge_ctrl,
            "editing": editing_ctrl,
            "stats": stats_ctrl,
            "about": about_ctrl,
        }
        window = create_main_window(theme, controllers)
        yield (
            window,
            theme,
            workspace_ctrl,
            clean_ctrl,
            merge_ctrl,
            editing_ctrl,
            stats_ctrl,
            about_ctrl,
        )
        window.deleteLater()
        qapp.processEvents()
