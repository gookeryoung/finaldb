"""主窗口：侧边栏 + 页面栈（QStackedWidget）+ 状态栏，全局快捷键。."""

from __future__ import annotations

from PySide2.QtGui import QKeySequence
from PySide2.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QShortcut,
    QStackedWidget,
    QWidget,
)

from finaldb.app_controllers import Controllers
from finaldb.gui.controllers.editing_controller import EditingController
from finaldb.gui.theme import ThemeManager
from finaldb.gui.widgets.pages.about_page import AboutPage
from finaldb.gui.widgets.pages.data_page import DataPage
from finaldb.gui.widgets.pages.settings_page import SettingsPage
from finaldb.gui.widgets.pages.stats_page import StatsPage
from finaldb.gui.widgets.sidebar import Sidebar

__all__ = ["PAGE_ORDER", "MainWindow"]

# 页面顺序（Ctrl+1..4 对应索引）
PAGE_ORDER = ["data", "stats", "settings", "about"]


class MainWindow(QMainWindow):
    """四页导航主窗口。."""

    def __init__(self, theme: ThemeManager, controllers: Controllers, parent: QWidget | None = None) -> None:
        """初始化主窗口并组装侧边栏与页面栈。

        Args:
            theme: 主题管理器
            controllers: 页面控制器装配表（key 见 ``finaldb.app_controllers``）
            parent: 父部件
        """
        super().__init__(parent)
        self.setWindowTitle("finaldb")
        self.resize(1080, 680)
        self.setMinimumSize(880, 560)
        self._theme = theme
        self._current = "data"

        central = QWidget(self)
        root = QHBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        self.sidebar = Sidebar(theme)
        root.addWidget(self.sidebar)

        self.stack = QStackedWidget()
        self.pages = {
            "data": DataPage(
                theme,
                controllers["workspace"],
                controllers["editing"],
                controllers["clean"],
                controllers["merge"],
            ),
            "stats": StatsPage(theme, controllers["workspace"], controllers["stats"]),
            "settings": SettingsPage(theme, controllers["workspace"], controllers["about"]),
            "about": AboutPage(theme, controllers["about"]),
        }
        for page_id in PAGE_ORDER:
            self.stack.addWidget(self.pages[page_id])
        root.addWidget(self.stack, stretch=1)

        self.setCentralWidget(central)

        # ---------- 状态栏：保存状态（编辑即时落库，每次操作后更新） ----------
        self._saved_label = QLabel("就绪")
        self._saved_label.setObjectName("statusSaved")
        self.statusBar().addWidget(self._saved_label)
        editing = controllers["editing"]
        if isinstance(editing, EditingController):
            editing.saved.connect(self._saved_label.setText)  # pyrefly: ignore [missing-attribute]

        self.sidebar.page_requested.connect(self.set_current_page)  # pyrefly: ignore [missing-attribute]
        self.stack.currentChanged.connect(self._on_stack_changed)
        self._build_shortcuts()
        self.sidebar.set_current_page("data")

    # ----------------------------- 对外 API -----------------------------

    def current_page(self) -> str:
        """当前页面标识。."""
        return self._current

    def set_current_page(self, page_id: str) -> None:
        """切换到指定页面（未知标识忽略）。."""
        if page_id not in self.pages:
            return
        self._current = page_id
        self.stack.setCurrentWidget(self.pages[page_id])

    def toggle_sidebar(self) -> None:
        """折叠/展开侧边栏（Ctrl+B）。."""
        self.sidebar.setVisible(not self.sidebar.isVisible())

    # ----------------------------- 内部 -----------------------------

    def _on_stack_changed(self, index: int) -> None:
        """页面栈切换后同步侧边栏选中态。."""
        widget = self.stack.widget(index)
        for page_id, page in self.pages.items():
            if page is widget:
                self._current = page_id
                self.sidebar.set_current_page(page_id)
                return

    def _build_shortcuts(self) -> None:
        """注册全局快捷键：Ctrl+1..4 切页，Ctrl+B 折叠侧边栏。."""
        for i, page_id in enumerate(PAGE_ORDER, start=1):
            shortcut = QShortcut(QKeySequence(f"Ctrl+{i}"), self)
            shortcut.activated.connect(lambda pid=page_id: self.set_current_page(pid))
        fold = QShortcut(QKeySequence("Ctrl+B"), self)
        fold.activated.connect(self.toggle_sidebar)
