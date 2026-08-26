"""清洗引擎测试：规则校验、单元格变换、报告统计。."""

from __future__ import annotations

from typing import Any

import pytest

from finaldb.core.cleaning.engine import CleanReport, apply_rules, validate_rules
from finaldb.core.cleaning.rules import CaseMode, CleanRule, RuleKind
from finaldb.core.exceptions import CleanError

COLUMNS = ["name", "age", "city"]


def _rule(kind: RuleKind, column: str = "name", **kwargs: Any) -> CleanRule:
    """构造测试规则。."""
    return CleanRule(kind=kind, column=column, **kwargs)


def test_validate_rules_rejects_empty() -> None:
    """空规则列表报错。."""
    with pytest.raises(CleanError, match="至少需要一条"):
        validate_rules(COLUMNS, [])


def test_validate_rules_rejects_unknown_column() -> None:
    """引用不存在的列报错。."""
    with pytest.raises(CleanError, match="不存在的列"):
        validate_rules(COLUMNS, [_rule(RuleKind.TRIM, column="nope")])
    # 空列名同样命中
    with pytest.raises(CleanError, match="不存在的列"):
        validate_rules(COLUMNS, [_rule(RuleKind.TRIM, column="")])


@pytest.mark.parametrize(
    "rule",
    [
        CleanRule(RuleKind.REPLACE, "name", value=""),
        CleanRule(RuleKind.FILL_MISSING, "city", value=""),
    ],
)
def test_validate_rules_requires_param(rule: CleanRule) -> None:
    """REPLACE/FILL_MISSING 缺参数报错。."""
    with pytest.raises(CleanError, match="缺少参数"):
        validate_rules(COLUMNS, [rule])


def test_trim_rule() -> None:
    """TRIM 去除首尾空白，非字符串与无变化单元格不计命中。."""
    rows = [(" 甲 ", 30, "BJ"), (None, 25, "SH"), ("乙", 40, "GZ")]
    out, report = apply_rules(COLUMNS, rows, [_rule(RuleKind.TRIM)])
    result = list(out)
    assert result == [("甲", 30, "BJ"), (None, 25, "SH"), ("乙", 40, "GZ")]
    assert report.total_rows == 3
    assert report.changed_cells == [1]
    assert report.dropped_rows == 0


@pytest.mark.parametrize(
    ("mode", "expected"),
    [(CaseMode.UPPER, ["ABC", "DEF"]), (CaseMode.LOWER, ["abc", "def"])],
)
def test_case_rule(mode: CaseMode, expected: list[str]) -> None:
    """CASE 大小写标准化，非字符串单元格跳过。."""
    rows = [("AbC", 1, "x"), ("DeF", 2, "y"), (3, 3, "z")]
    out, report = apply_rules(COLUMNS, rows, [CleanRule(RuleKind.CASE, "name", case_mode=mode)])
    assert [r[0] for r in out] == [*expected, 3]
    assert report.changed_cells == [2]


def test_replace_rule() -> None:
    """REPLACE 全量替换文本，非字符串跳过。."""
    rows = [("a-b", 1, "x"), ("a-b-c", 2, "y"), (None, 3, "z")]
    rule = CleanRule(RuleKind.REPLACE, "name", value="-", replacement="_")
    out, report = apply_rules(COLUMNS, rows, [rule])
    assert [r[0] for r in out] == ["a_b", "a_b_c", None]
    assert report.changed_cells == [2]


def test_to_number_rule() -> None:
    """TO_NUMBER 文本转数值：int/float 成功，失败保留原文。."""
    rows = [("12", "3.5", "abc"), (None, "7", "x")]
    out, report = apply_rules(["a", "b", "c"], rows, [_rule(RuleKind.TO_NUMBER, "b")])
    result = list(out)
    assert result[0][1] == 3.5
    assert result[1][1] == 7
    assert report.changed_cells == [2]
    # 数值与 None 原样保留
    out2, report2 = apply_rules(["a", "b", "c"], [(1, 2.5, None)], [_rule(RuleKind.TO_NUMBER, "a")])
    assert list(out2) == [(1, 2.5, None)]
    assert report2.changed_cells == [0]


def test_fill_missing_rule() -> None:
    """FILL_MISSING 填充 None；填充值尽量解析为数值。."""
    rows = [(None, 1, "x"), ("有值", 2, None)]
    rule = CleanRule(RuleKind.FILL_MISSING, "name", value="0")
    out, report = apply_rules(COLUMNS, rows, [rule])
    result = list(out)
    assert result[0][0] == 0
    assert result[1][0] == "有值"
    assert report.changed_cells == [1]


def test_fill_missing_keeps_text() -> None:
    """非数值填充值保留为文本。."""
    out, report = apply_rules(COLUMNS, [("有值", 1, None)], [CleanRule(RuleKind.FILL_MISSING, "city", value="未知")])
    assert next(iter(out))[2] == "未知"
    assert report.changed_cells == [1]


def test_drop_missing_rule() -> None:
    """DROP_MISSING 删除该列为 None 的行。"""
    rows = [("甲", None, "x"), ("乙", 2, "y"), ("丙", None, "z")]
    out, report = apply_rules(COLUMNS, rows, [_rule(RuleKind.DROP_MISSING, "age")])
    assert list(out) == [("乙", 2, "y")]
    assert report.dropped_rows == 2
    assert report.total_rows == 3
    assert report.changed_cells == [0]


def test_multiple_rules_apply_in_order() -> None:
    """多规则按声明顺序依次应用（TRIM 后 TO_NUMBER 可解析带空白数字）。."""
    rows = [(" 12 ", "X")]
    rules = [_rule(RuleKind.TRIM, "name"), _rule(RuleKind.TO_NUMBER, "name")]
    out, report = apply_rules(["name", "flag"], rows, rules)
    assert list(out) == [(12, "X")]
    assert report.changed_cells == [1, 1]


def test_drop_missing_stops_later_rules() -> None:
    """行被 DROP_MISSING 删除后不再应用后续规则。."""
    rows = [(None, 1), (None, 2)]
    rules = [_rule(RuleKind.DROP_MISSING, "name"), _rule(RuleKind.FILL_MISSING, "name", value="x")]
    out, report = apply_rules(["name", "n"], rows, rules)
    assert list(out) == []
    assert report.dropped_rows == 2
    assert report.changed_cells == [0, 0]


def test_report_counts_lazily() -> None:
    """报告随迭代器消费累积，未消费时 total_rows 为 0。."""
    rows = iter([(" 甲 ", 1), ("乙", 2)])
    out, report = apply_rules(COLUMNS[:2], rows, [_rule(RuleKind.TRIM)])
    assert report.total_rows == 0
    next(out)
    assert report.total_rows == 1
    list(out)
    assert report.total_rows == 2


def test_report_format_lines() -> None:
    """报告格式化：含读入/删除行数与规则命中数。."""
    report = CleanReport(total_rows=10, dropped_rows=3, changed_cells=[5, 0])
    rules = [_rule(RuleKind.TRIM), _rule(RuleKind.CASE)]
    lines = report.format_lines(rules)
    assert "读入行数: 10" in lines
    assert "删除行数: 3" in lines
    assert any("去除首尾空白" in line and "5 处" in line for line in lines)
    # 命中 0 的规则不出现在输出
    assert not any("转小写" in line for line in lines)


def test_report_format_lines_no_change() -> None:
    """无任何命中时提示未发现需要清洗的数据。."""
    report = CleanReport(total_rows=4, changed_cells=[0])
    lines = report.format_lines([_rule(RuleKind.TRIM)])
    assert "未发现需要清洗的数据" in lines


def test_rule_describe() -> None:
    """规则描述包含列名与参数。."""
    rule = CleanRule(RuleKind.REPLACE, "name", value="-", replacement="_")
    assert "「name」" in rule.describe()
    assert "「-」→「_」" in rule.describe()


@pytest.mark.parametrize(
    "rule",
    [
        CleanRule(RuleKind.TRIM, "name"),
        CleanRule(RuleKind.CASE, "name"),
        CleanRule(RuleKind.TO_NUMBER, "age"),
        CleanRule(RuleKind.FILL_MISSING, "city", value="未知"),
        CleanRule(RuleKind.DROP_MISSING, "age"),
    ],
)
def test_rule_describe_all_kinds(rule: CleanRule) -> None:
    """全部规则种类都能生成包含列名的描述。."""
    described = rule.describe()
    assert f"「{rule.column}」" in described


def test_fill_missing_float_value() -> None:
    """浮点填充值解析为 float。."""
    out, _report = apply_rules(COLUMNS, [(None, 1, "x")], [CleanRule(RuleKind.FILL_MISSING, "name", value="2.5")])
    assert next(iter(out))[0] == 2.5
