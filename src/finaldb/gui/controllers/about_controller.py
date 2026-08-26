"""关于控制器：暴露应用版本与环境信息给 QML 关于页。."""

from __future__ import annotations

import sys

import dulwich
import PySide2
from PySide2.QtCore import Property, QObject, qVersion

import finaldb

__all__ = ["AboutController"]

# 开源许可文案（MIT）
_LICENSE = "MIT License"


class AboutController(QObject):
    """关于页控制器（QML 绑定 ``AboutCtrl``）。."""

    def _get_version(self) -> str:
        """finaldb 版本号。."""
        return finaldb.__version__

    version = Property(str, _get_version, constant=True)

    def _get_python_version(self) -> str:
        """Python 解释器版本。."""
        return sys.version.split()[0]

    pythonVersion = Property(str, _get_python_version, constant=True)

    def _get_qt_version(self) -> str:
        """Qt 运行时版本。."""
        return str(qVersion() or "unknown")

    qtVersion = Property(str, _get_qt_version, constant=True)

    def _get_pyside2_version(self) -> str:
        """PySide2 绑定版本。."""
        return PySide2.__version__

    pyside2Version = Property(str, _get_pyside2_version, constant=True)

    def _get_dulwich_version(self) -> str:
        """dulwich（git 引擎）版本。."""
        return ".".join(str(part) for part in dulwich.__version__)

    dulwichVersion = Property(str, _get_dulwich_version, constant=True)

    def _get_license(self) -> str:
        """开源许可类型。."""
        return _LICENSE

    licenseText = Property(str, _get_license, constant=True)
