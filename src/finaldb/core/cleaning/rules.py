"""清洗规则定义：规则种类/大小写模式枚举 + 规则数据类。."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

__all__ = ["CaseMode", "CleanRule", "RuleKind"]


class RuleKind(Enum):
    """清洗规则种类。."""

    TRIM = "trim"  # 去除首尾空白
    CASE = "case"  # 大小写标准化
    REPLACE = "replace"  # 文本替换
    TO_NUMBER = "to_number"  # 文本转数值
    FILL_MISSING = "fill_missing"  # 缺失值填充
    DROP_MISSING = "drop_missing"  # 缺失行删除


class CaseMode(Enum):
    """大小写标准化模式。."""

    UPPER = "upper"
    LOWER = "lower"


@dataclass(frozen=True)
class CleanRule:
    """一条清洗规则：对指定列应用一种变换。

    :ivar kind: 规则种类
    :ivar column: 目标列名（须在表列中存在）
    :ivar value: FILL_MISSING 的填充值 / REPLACE 的查找文本
    :ivar replacement: REPLACE 的替换文本
    :ivar case_mode: CASE 的大小写模式
    """

    kind: RuleKind
    column: str
    value: str = ""
    replacement: str = ""
    case_mode: CaseMode = CaseMode.LOWER

    def describe(self) -> str:
        """规则的人类可读描述（规则列表展示用）。."""
        if self.kind is RuleKind.TRIM:
            return f"「{self.column}」去除首尾空白"
        if self.kind is RuleKind.CASE:
            mode = "转大写" if self.case_mode is CaseMode.UPPER else "转小写"
            return f"「{self.column}」{mode}"
        if self.kind is RuleKind.REPLACE:
            return f"「{self.column}」替换「{self.value}」→「{self.replacement}」"
        if self.kind is RuleKind.TO_NUMBER:
            return f"「{self.column}」文本转数值"
        if self.kind is RuleKind.FILL_MISSING:
            return f"「{self.column}」缺失填充为「{self.value}」"
        return f"「{self.column}」缺失行删除"
