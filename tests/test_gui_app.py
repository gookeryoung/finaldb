"""app.py 入口装配测试：字体、类型注册、引擎与应用构造。."""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.gui


def test_apply_global_font(qapp: object) -> None:
    """apply_global_font 应设置应用级字体且不抛异常。."""
    from PySide2.QtGui import QGuiApplication

    from finaldb.app import apply_global_font

    app = QGuiApplication.instance()
    assert app is not None
    apply_global_font(app)
    # 字体族回退列表首项应为平台默认字体
    families = app.font().families()
    assert isinstance(families, list)


def test_register_qml_types_idempotent() -> None:
    """register_qml_types 重复调用应幂等（守卫标志生效，不重复注册）。."""
    from finaldb.app import register_qml_types

    register_qml_types()
    assert getattr(register_qml_types, "done", False) is True
    # 第二次调用直接短路返回，不触发 QML 重复注册
    register_qml_types()
    assert getattr(register_qml_types, "done", False) is True


def test_create_app_assembles_engine(qapp: object) -> None:
    """create_app 应返回 (应用, 引擎, 主题) 且 Main.qml 成功加载。."""
    from finaldb.app import create_app

    app, engine, theme = create_app([])
    assert app is not None
    assert engine.rootObjects(), "create_app 未加载 Main.qml"
    assert theme is not None
    assert theme.isDark is False
