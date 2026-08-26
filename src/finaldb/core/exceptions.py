"""core 层统一异常体系：公共基类 + 按场景分类。."""

from __future__ import annotations

__all__ = [
    "CleanError",
    "FinaldbError",
    "InvalidDataError",
    "MergeError",
    "TableExistsError",
    "UnsupportedFormatError",
    "VersionError",
    "WorkspaceError",
]


class FinaldbError(Exception):
    """finaldb 所有业务异常的公共基类。."""


class CleanError(FinaldbError):
    """数据整理相关错误（规则校验失败、源表不存在等）。"""


class MergeError(FinaldbError):
    """合并/去重相关错误（表或键列不存在、模式不支持等）。"""


class WorkspaceError(FinaldbError):
    """工作区生命周期相关错误（创建/打开/校验失败）。"""


class TableExistsError(FinaldbError):
    """目标表已存在（导入/合并的目标表名冲突）。"""


class UnsupportedFormatError(FinaldbError):
    """文件格式不受支持（无法识别的扩展名或损坏的文件）。"""


class InvalidDataError(FinaldbError):
    """数据内容不合法（空文件、结构不一致等）。"""


class VersionError(FinaldbError):
    """版本控制相关错误（快照不存在、引用无法解析等）。"""
