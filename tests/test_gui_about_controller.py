"""关于控制器测试：版本与环境信息属性。."""

from __future__ import annotations

import pytest

import finaldb
from finaldb.gui.controllers.about_controller import AboutController

pytestmark = pytest.mark.gui


@pytest.fixture()
def about_ctrl() -> AboutController:
    """每个用例独立的关于控制器。."""
    return AboutController()


def test_version_matches_package(about_ctrl: AboutController) -> None:
    """version 属性与包版本一致。."""
    assert about_ctrl.version() == finaldb.__version__


def test_python_version(about_ctrl: AboutController) -> None:
    """pythonVersion 为解释器主版本号。."""
    import sys

    assert about_ctrl.python_version() == sys.version.split()[0]


def test_runtime_versions(about_ctrl: AboutController) -> None:
    """Qt/PySide2/dulwich 版本非空。."""
    assert about_ctrl.qt_version()
    assert about_ctrl.pyside2_version()
    assert about_ctrl.dulwich_version()


def test_license_text(about_ctrl: AboutController) -> None:
    """开源许可为 MIT。."""
    assert about_ctrl.license_text() == "MIT License"
