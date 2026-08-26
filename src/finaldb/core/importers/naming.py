"""标识符清洗：任意文本 → SQLite 合法标识符（保留 Unicode 字母数字）。."""

from __future__ import annotations

import re

__all__ = ["sanitize_identifier"]

# 分隔符与危险字符替换为下划线（引号/空白/控制符/路径符号）
_INVALID_RE = re.compile(r'["\'\s\x00-\x1f\x7f/\\:;]+')
# 开头数字前补前缀（保持可读性）
_LEADING_DIGIT_RE = re.compile(r"^([0-9])")


def sanitize_identifier(text: str) -> str:
    """清洗为合法 SQL 标识符（保留中文等 Unicode 字母数字）。

    清洗后为空时回退 ``table``。

    :param text: 原始文本
    :return: 合法标识符（非空）
    """
    cleaned = _INVALID_RE.sub("_", text.strip())
    cleaned = _LEADING_DIGIT_RE.sub(r"n\1", cleaned)
    cleaned = cleaned.strip("_")
    return cleaned or "table"
