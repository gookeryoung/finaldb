"""app.py 入口装配测试：字体、类型注册、引擎与应用构造。."""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

pytestmark = pytest.mark.gui


def test_main_qml_path_source_mode() -> None:
    """源码运行时主 QML 路径应指向包内 views 目录。."""
    from finaldb.app import _main_qml_path

    path = _main_qml_path()
    assert path.name == "Main.qml"
    assert path.is_file()


def test_main_qml_path_frozen_mode(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """冻结模式（_MEIPASS 存在且文件在位）应返回解包目录路径。."""
    from finaldb.app import _main_qml_path

    frozen = tmp_path / "finaldb" / "gui" / "views" / "Main.qml"
    frozen.parent.mkdir(parents=True)
    frozen.write_text("// mock", encoding="utf-8")
    monkeypatch.setattr(sys, "_MEIPASS", str(tmp_path), raising=False)
    assert _main_qml_path() == frozen


def test_main_qml_path_frozen_missing(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """冻结模式但解包目录缺文件时应回退源码路径。."""
    from finaldb.app import _main_qml_path

    monkeypatch.setattr(sys, "_MEIPASS", str(tmp_path), raising=False)
    assert _main_qml_path().is_file()


def test_setup_frozen_paths_sets_qml_import(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """冻结模式下存在 Qt/qml 目录时应设置 QML2_IMPORT_PATH。."""
    from finaldb.app import _setup_frozen_paths

    qml_dir = tmp_path / "PySide2" / "Qt" / "qml"
    qml_dir.mkdir(parents=True)
    monkeypatch.setattr(sys, "_MEIPASS", str(tmp_path), raising=False)
    monkeypatch.setenv("QML2_IMPORT_PATH", "")
    _setup_frozen_paths()
    assert os.environ["QML2_IMPORT_PATH"] == str(qml_dir)


def test_setup_frozen_paths_noop_in_source(monkeypatch: pytest.MonkeyPatch) -> None:
    """源码运行（无 _MEIPASS）时应为空操作且不动环境变量。."""
    from finaldb.app import _setup_frozen_paths

    monkeypatch.delattr(sys, "_MEIPASS", raising=False)
    monkeypatch.setenv("QML2_IMPORT_PATH", "")
    _setup_frozen_paths()
    assert os.environ["QML2_IMPORT_PATH"] == ""


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
