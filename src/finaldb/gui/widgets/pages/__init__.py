"""pages 门面：仅做 re-export。."""

from __future__ import annotations

from finaldb.gui.widgets.pages.about_page import AboutPage
from finaldb.gui.widgets.pages.clean_pane import CleanPane
from finaldb.gui.widgets.pages.data_page import DataPage
from finaldb.gui.widgets.pages.edit_panel import EditPanel
from finaldb.gui.widgets.pages.merge_pane import MergePane
from finaldb.gui.widgets.pages.settings_page import SettingsPage
from finaldb.gui.widgets.pages.stats_page import StatsPage

__all__ = [
    "AboutPage",
    "CleanPane",
    "DataPage",
    "EditPanel",
    "MergePane",
    "SettingsPage",
    "StatsPage",
]
