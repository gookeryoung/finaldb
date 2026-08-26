"""GUI 测试共享 fixture：Qt 离屏环境与 QML 引擎装配。."""

from __future__ import annotations

import os
import tempfile
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

# 必须在导入 PySide2 前设置：无头/CI 环境用离屏平台；
# 禁用 QML 磁盘缓存：避免缓存污染导致引擎加载异常
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_QML_DISABLE_DISK_CACHE", "1")

from PySide2.QtCore import QObject
from PySide2.QtGui import QGuiApplication
from PySide2.QtQuick import QQuickItem

_VIEWS_DIR = Path(__file__).parents[1] / "src" / "finaldb" / "gui" / "views"


@pytest.fixture(scope="session")
def qapp() -> Iterator[QGuiApplication]:
    """会话级 QGuiApplication 单例。."""
    app = QGuiApplication.instance() or QGuiApplication([])
    yield app
    app.processEvents()


@pytest.fixture()
def qml_engine(qapp: QGuiApplication) -> Iterator[tuple[Any, ...]]:
    """装配完整 QML 应用（注册类型 + 控制器 + 加载 Main.qml）。

    控制器使用临时工作区根目录，避免污染用户主目录。

    Yields:
        (QML 引擎, 主题控制器, 主窗口根对象, 工作区控制器, 预览控制器, 清洗控制器)
    """
    from finaldb.app import apply_global_font, create_engine, register_qml_types
    from finaldb.gui.controllers.clean_controller import CleanController
    from finaldb.gui.controllers.preview_controller import PreviewController
    from finaldb.gui.controllers.workspace_controller import WorkspaceController
    from finaldb.gui.theme import ThemeController

    apply_global_font(qapp)
    register_qml_types()
    theme = ThemeController()
    with tempfile.TemporaryDirectory() as tmp:
        workspace_ctrl = WorkspaceController(root=Path(tmp))
        preview_ctrl = PreviewController()
        clean_ctrl = CleanController()
        engine = create_engine(theme, (workspace_ctrl, preview_ctrl, clean_ctrl))
        assert engine.rootObjects(), "Main.qml 加载失败"
        root = engine.rootObjects()[0]
        yield engine, theme, root, workspace_ctrl, preview_ctrl, clean_ctrl
        engine.deleteLater()
        qapp.processEvents()


def find_sidebar(root: QObject) -> QQuickItem:
    """按 objectName 查找侧边栏 QQuickItem。."""
    item = root.findChild(QQuickItem, "sidebar")
    assert item is not None, "未找到侧边栏"
    return item


def qml_prop(obj: QObject, name: str) -> Any:
    """读取 QQuickItem 动态属性（PySide2 类型桩将 name 推断为 bytes）。."""
    return obj.property(name)  # pyrefly: ignore [bad-argument-type]


def qml_set_prop(obj: QObject, name: str, value: Any) -> None:
    """写入 QQuickItem 动态属性（PySide2 类型桩将 name 推断为 bytes）。."""
    obj.setProperty(name, value)  # pyrefly: ignore [bad-argument-type]
