"""finaldb GUI 应用入口：构造 QGuiApplication 与 QQmlApplicationEngine。

仅支持 PySide2（Win7 发布目标），运行时环境为 Python 3.10。
"""

from __future__ import annotations

import sys
from pathlib import Path

from PySide2.QtCore import QObject, QUrl
from PySide2.QtGui import QFont, QGuiApplication
from PySide2.QtQml import QQmlApplicationEngine, qmlRegisterType

from finaldb.gui.controllers.preview_controller import PreviewController
from finaldb.gui.controllers.workspace_controller import WorkspaceController
from finaldb.gui.theme import ThemeController, detect_font_families

__all__ = ["apply_global_font", "create_app", "create_engine", "main"]

_MAIN_QML = Path(__file__).parent / "gui" / "views" / "Main.qml"


def apply_global_font(app: QGuiApplication) -> None:
    """设置全局字体族回退与默认字号。

    用 ``QFont.setFamilies()`` 设置优先级列表，Qt 自动选择首个可用字体。
    """
    font = QFont()
    font.setFamilies(list(detect_font_families()))
    font.setPixelSize(14)
    app.setFont(font)


def register_qml_types() -> None:
    """注册 Python 类型到 QML 类型系统（幂等，重复调用只注册一次）。

    qmlRegisterType 重复注册同一 (URI, version, name) 会导致 QML import
    失败（多引擎/多测试场景），故在函数对象上挂守卫标志只注册一次。
    """
    if getattr(register_qml_types, "done", False):
        return
    # URI=FinalDB.Theme，QML 用 `import FinalDB.Theme 1.0` 后声明
    # `property ThemeController theme: Theme` 类型化访问 context property
    qmlRegisterType(ThemeController, "FinalDB.Theme", 1, 0, "ThemeController")  # pyrefly: ignore [bad-argument-type]
    register_qml_types.done = True  # type: ignore[attr-defined]


def create_controllers() -> tuple[WorkspaceController, PreviewController]:
    """构造页面控制器（以 context property 暴露给 QML）。

    Returns:
        (工作区控制器, 表预览控制器) 二元组
    """
    return WorkspaceController(), PreviewController()


def create_engine(
    theme: ThemeController,
    controllers: tuple[WorkspaceController, PreviewController] | None = None,
    parent: QObject | None = None,
) -> QQmlApplicationEngine:
    """构造 QML 引擎并加载主窗口。

    Args:
        theme: 主题控制器单例，以 context property ``Theme`` 暴露给 QML
        controllers: 页面控制器二元组（None 时新建）
        parent: 引擎父对象

    Returns:
        已加载 ``Main.qml`` 的引擎（加载失败时 rootObjects 为空）
    """
    if controllers is None:
        controllers = create_controllers()
    workspace_ctrl, preview_ctrl = controllers
    engine = QQmlApplicationEngine(parent)
    ctx = engine.rootContext()
    ctx.setContextProperty("Theme", theme)  # pyrefly: ignore [missing-argument]
    ctx.setContextProperty("WorkspaceCtrl", workspace_ctrl)  # pyrefly: ignore [missing-argument]
    ctx.setContextProperty("PreviewCtrl", preview_ctrl)  # pyrefly: ignore [missing-argument]
    engine.load(QUrl.fromLocalFile(str(_MAIN_QML)))  # pyrefly: ignore [missing-argument]
    return engine


def create_app(
    argv: list[str], controllers: tuple[WorkspaceController, PreviewController] | None = None
) -> tuple[QGuiApplication, QQmlApplicationEngine, ThemeController]:
    """构造完整 GUI 应用（可测函数，拆离事件循环）。

    Args:
        argv: 命令行参数（透传 QGuiApplication）
        controllers: 页面控制器二元组（None 时新建）

    Returns:
        (应用实例, QML 引擎, 主题控制器) 三元组
    """
    app = QGuiApplication.instance() or QGuiApplication(argv)
    apply_global_font(app)
    register_qml_types()
    theme = ThemeController()
    engine = create_engine(theme, controllers)
    return app, engine, theme


def main() -> int:  # pragma: no cover
    """启动 GUI 应用（事件循环阻塞，需图形环境手动测试）。"""
    app, engine, _theme = create_app(sys.argv)
    if not engine.rootObjects():
        return 1
    return app.exec_()


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
