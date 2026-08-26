"""finaldb 基础冒烟测试."""

from __future__ import annotations

import finaldb


def test_version_is_string() -> None:
    """__version__ 应为非空字符串."""
    assert isinstance(finaldb.__version__, str)
    assert finaldb.__version__


def test_package_importable() -> None:
    """包应可正常导入."""
    assert hasattr(finaldb, "__all__")
    assert "__version__" in finaldb.__all__
