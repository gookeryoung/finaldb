"""finaldb GUI 应用入口：构造 QApplication（Widgets）与主窗口。

仅支持 PySide2（Win7 发布目标），运行时环境为 Python 3.10。
"""

from __future__ import annotations

import sys

from PySide2.QtCore import QObject
from PySide2.QtGui import QFont, QGuiApplication
from PySide2.QtWidgets import QApplication, QMainWindow

from finaldb.app_controllers import Controllers, create_controllers
from finaldb.gui.theme import ThemeManager, build_qss, detect_font_families
from finaldb.gui.widgets.main_window import MainWindow

__all__ = ["apply_global_font", "apply_theme", "create_app", "create_main_window", "main"]


def apply_global_font(app: QGuiApplication) -> None:
    """设置全局字体族回退与默认字号。

    用 ``QFont.setFamilies()`` 设置优先级列表，Qt 自动选择首个可用字体。
    """
    font = QFont()
    font.setFamilies(list(detect_font_families()))
    font.setPixelSize(14)
    app.setFont(font)


def apply_theme(app: QApplication, theme: ThemeManager) -> None:
    """生成当前主题 QSS 并整体应用到应用。."""
    app.setStyleSheet(build_qss(theme))


def create_main_window(theme: ThemeManager, controllers: Controllers, parent: QObject | None = None) -> QMainWindow:
    """构造主窗口（可测函数，与事件循环解耦）。

    Args:
        theme: 主题管理器
        controllers: 页面控制器装配表（key 见 ``finaldb.app_controllers``）
        parent: 父对象

    Returns:
        已装配侧边栏与七页栈的主窗口
    """
    return MainWindow(theme, controllers, parent)


def create_app(
    argv: list[str], controllers: Controllers | None = None
) -> tuple[QApplication, MainWindow, ThemeManager]:
    """构造完整 GUI 应用（可测函数，拆离事件循环）。

    Args:
        argv: 命令行参数（透传 QApplication）
        controllers: 页面控制器装配表（None 时新建）

    Returns:
        (应用实例, 主窗口, 主题管理器) 三元组
    """
    app = QApplication.instance() or QApplication(argv)
    app.setStyle("Fusion")
    apply_global_font(app)
    theme = ThemeManager()
    apply_theme(app, theme)
    theme.theme_changed.connect(lambda: apply_theme(app, theme))  # pyrefly: ignore [missing-attribute]
    window = create_main_window(theme, controllers or create_controllers())
    return app, window, theme


def main() -> int:  # pragma: no cover
    """启动 GUI 应用（事件循环阻塞，需图形环境手动测试）。"""
    app, window, _theme = create_app(sys.argv)
    window.show()
    return app.exec_()


if __name__ == "__main__":  # pragma: no cover
    # 模块直跑入口：fspack wrapper 经 run_module 以 __main__ 执行本模块，
    # 无此守卫时模块体执行完即静默退出（无窗口、退出码 0）。
    sys.exit(main())
