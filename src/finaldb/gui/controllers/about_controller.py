"""关于控制器：暴露应用版本与环境信息给关于页。."""

from __future__ import annotations

import sys

import dulwich
import PySide2
from PySide2.QtCore import QObject, qVersion

import finaldb

__all__ = ["AboutController"]

# 开源许可文案（MIT）
_LICENSE = "MIT License"


class AboutController(QObject):
    """关于页控制器。."""

    def version(self) -> str:
        """finaldb 版本号。."""
        return finaldb.__version__

    def python_version(self) -> str:
        """Python 解释器版本。."""
        return sys.version.split()[0]

    def qt_version(self) -> str:
        """Qt 运行时版本。."""
        return str(qVersion() or "unknown")

    def pyside2_version(self) -> str:
        """PySide2 绑定版本。."""
        return PySide2.__version__

    def dulwich_version(self) -> str:
        """dulwich（git 引擎）版本。."""
        return ".".join(str(part) for part in dulwich.__version__)

    def license_text(self) -> str:
        """开源许可类型。."""
        return _LICENSE
