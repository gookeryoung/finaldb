"""pages 门面：仅做 re-export。."""

from __future__ import annotations

from finaldb.gui.widgets.pages.about_page import AboutPage
from finaldb.gui.widgets.pages.clean_page import CleanPage
from finaldb.gui.widgets.pages.history_page import HistoryPage
from finaldb.gui.widgets.pages.home_page import HomePage
from finaldb.gui.widgets.pages.merge_page import MergePage
from finaldb.gui.widgets.pages.settings_page import SettingsPage
from finaldb.gui.widgets.pages.stats_page import StatsPage

__all__ = [
    "AboutPage",
    "CleanPage",
    "HistoryPage",
    "HomePage",
    "MergePage",
    "SettingsPage",
    "StatsPage",
]
