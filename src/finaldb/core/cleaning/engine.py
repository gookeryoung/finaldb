"""清洗引擎：把规则流式应用到行迭代器，报告随行消费累积。."""

from __future__ import annotations

from collections.abc import Iterable, Iterator, Sequence
from dataclasses import dataclass, field

from finaldb.core.cleaning.rules import CaseMode, CleanRule, RuleKind
from finaldb.core.exceptions import CleanError

__all__ = ["CleanReport", "apply_rules", "validate_rules"]


@dataclass
class CleanReport:
    """清洗执行统计（迭代器耗尽时统计完毕）。

    :ivar total_rows: 读入行数（含被删除的行）
    :ivar dropped_rows: 因 DROP_MISSING 删除的行数
    :ivar changed_cells: 每条规则命中的单元格数（与规则列表等长）
    """

    total_rows: int = 0
    dropped_rows: int = 0
    changed_cells: list[int] = field(default_factory=list)

    def format_lines(self, rules: Sequence[CleanRule]) -> list[str]:
        """把统计格式化为界面可读的文本行。."""
        lines = [f"读入行数: {self.total_rows}"]
        if self.dropped_rows:
            lines.append(f"删除行数: {self.dropped_rows}")
        for rule, hits in zip(rules, self.changed_cells, strict=False):
            if hits:
                lines.append(f"{rule.describe()}: {hits} 处")
        if not self.dropped_rows and not any(self.changed_cells):
            lines.append("未发现需要清洗的数据")
        return lines


def validate_rules(columns: Sequence[str], rules: Sequence[CleanRule]) -> None:
    """校验规则与表列的匹配性，不合法即抛 :class:`CleanError`。

    :param columns: 表列名列表
    :param rules: 待应用的规则列表
    :raises CleanError: 规则引用不存在的列，或参数缺失
    """
    if not rules:
        raise CleanError("至少需要一条清洗规则")
    known = set(columns)
    for rule in rules:
        if rule.column not in known:
            raise CleanError(f"规则引用了不存在的列: {rule.column}")
        if rule.kind in (RuleKind.REPLACE, RuleKind.FILL_MISSING) and not rule.value:
            raise CleanError(f"规则「{rule.describe()}」缺少参数")


def apply_rules(
    columns: Sequence[str],
    rows: Iterable[Sequence[object]],
    rules: Sequence[CleanRule],
) -> tuple[Iterator[tuple[object, ...]], CleanReport]:
    """流式应用规则，返回 (清洗后行迭代器, 统计报告)。

    报告计数随迭代器消费累积：预览场景取前 N 行得到的是样本统计。

    :param columns: 列名列表（决定单元格索引）
    :param rows: 原始行迭代器
    :param rules: 已通过校验的规则列表
    :return: (变换后的行元组迭代器, 报告对象)
    """
    validate_rules(columns, rules)
    index_of = {name: i for i, name in enumerate(columns)}
    # 预解析每条规则的目标列索引，行处理循环内不再查字典
    indices = [index_of[rule.column] for rule in rules]
    report = CleanReport(changed_cells=[0] * len(rules))
    return _transformed(rows, rules, indices, report), report


def _transformed(
    rows: Iterable[Sequence[object]],
    rules: Sequence[CleanRule],
    indices: Sequence[int],
    report: CleanReport,
) -> Iterator[tuple[object, ...]]:
    """行变换生成器：逐行应用规则并累积统计。."""
    for row in rows:
        report.total_rows += 1
        values = list(row)
        dropped = False
        for i, rule in enumerate(rules):
            cell = values[indices[i]]
            if rule.kind is RuleKind.DROP_MISSING:
                if cell is None:
                    report.dropped_rows += 1
                    dropped = True
                    break
                continue
            new_cell = _apply_cell(rule, cell)
            if new_cell != cell:
                values[indices[i]] = new_cell
                report.changed_cells[i] += 1
        if not dropped:
            yield tuple(values)


def _apply_cell(rule: CleanRule, cell: object) -> object:
    """对单个单元格应用非删除类规则。."""
    result: object = cell
    if rule.kind is RuleKind.TRIM:
        if isinstance(cell, str):
            result = cell.strip()
    elif rule.kind is RuleKind.CASE:
        if isinstance(cell, str):
            result = cell.upper() if rule.case_mode is CaseMode.UPPER else cell.lower()
    elif rule.kind is RuleKind.REPLACE:
        if isinstance(cell, str):
            result = cell.replace(rule.value, rule.replacement)
    elif rule.kind is RuleKind.TO_NUMBER:
        result = _parse_number(cell)
    elif rule.kind is RuleKind.FILL_MISSING:
        result = _parse_scalar(rule.value) if cell is None else cell
    return result


def _parse_number(cell: object) -> object:
    """文本单元格解析为 int/float，其余原样返回。."""
    if isinstance(cell, (int, float)) or cell is None:
        return cell
    text = str(cell).strip()
    try:
        return int(text)
    except ValueError:
        try:
            return float(text)
        except ValueError:
            return cell


def _parse_scalar(text: str) -> object:
    """填充值尽量解析为数值，失败保留原文。."""
    stripped = text.strip()
    try:
        return int(stripped)
    except ValueError:
        try:
            return float(stripped)
        except ValueError:
            return text
