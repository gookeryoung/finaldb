"""Widgets 页面测试：四页装配与页面/控制器联动交互。."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Tuple  # noqa: UP035  # 3.8 运行时下标兼容

import pytest

pytestmark = pytest.mark.gui

# main_window fixture 元组：(主窗口, 主题, 工作区/清洗/合并/编辑/统计/关于控制器)
WindowFixture = Tuple[Any, ...]  # noqa: UP006  # 3.8 运行时下标兼容


def _csv(tmp_path: Path, name: str, content: str) -> Path:
    """生成临时 CSV 文件。."""
    f = tmp_path / name
    f.write_text(content, "utf-8")
    return f


def _show(window: Any, qapp: Any, page_id: str) -> Any:
    """显示主窗口并切换到指定页面后返回页面实例。."""
    window.show()
    window.set_current_page(page_id)
    qapp.processEvents()
    return window.pages[page_id]


# ----------------------------- 数据页 -----------------------------


def test_data_workspace_and_table_flow(main_window: WindowFixture, tmp_path: Path, qapp: Any) -> None:
    """数据页联动：建工作区 → 导入 → 表列表点击进入编辑。."""
    window, _theme, ws, _clean, _merge, edit, *_rest = main_window
    data = _show(window, qapp, "data")

    ws.create_workspace("data-bind")
    csv = _csv(tmp_path, "d.csv", "name,age\n甲,30\n乙,25\n")
    ws.import_file_sync(str(csv))
    qapp.processEvents()

    # 工作区下拉与表列表刷新
    assert data._ws_combo.count() == 1
    assert data._ws_combo.currentText() == "data-bind"
    assert data._table_list.count() == 1
    assert data._table_list.item(0).text() == "d (2)"
    # 点击表项在右侧编辑面板打开编辑会话并切到编辑模式
    data._mode_group.button(1).setChecked(True)
    data._on_table_clicked(data._table_list.item(0))
    qapp.processEvents()
    assert edit.current_table() == "d"
    assert edit.edit_model().rowCount() == 2
    assert data._stack.currentIndex() == 0
    assert data._editor._view.isVisible()
    window.close()


def test_data_mode_switch(main_window: WindowFixture, qapp: Any) -> None:
    """数据页模式按钮组切换编辑/清洗/合并去重三个面板。."""
    window, *_rest = main_window
    data = _show(window, qapp, "data")
    assert data._stack.currentIndex() == 0
    for index in (1, 2, 0):
        data._mode_group.button(index).click()
        qapp.processEvents()
        assert data._stack.currentIndex() == index
    # 三面板互斥选中
    assert data._mode_group.button(0).isChecked()
    assert not data._mode_group.button(1).isChecked()
    window.close()


def test_data_workspace_combo_switch(main_window: WindowFixture, tmp_path: Path, qapp: Any) -> None:
    """数据页工作区下拉切换：表列表与编辑会话同步刷新。."""
    window, _theme, ws, *_rest = main_window
    data = _show(window, qapp, "data")

    ws.create_workspace("ws-a")
    ws.create_workspace("ws-b")
    csv_a = _csv(tmp_path, "a.csv", "x\n1\n")
    ws.select_workspace("ws-a")
    ws.import_file_sync(str(csv_a))
    qapp.processEvents()
    assert data._ws_combo.count() == 2
    assert data._table_list.count() == 1

    # 下拉切到 ws-b：表列表清空
    data._on_workspace_activated(1)
    qapp.processEvents()
    assert ws.current_workspace() == "ws-b"
    assert data._table_list.count() == 0
    window.close()


def test_data_new_and_delete_workspace_dialogs(
    main_window: WindowFixture, monkeypatch: pytest.MonkeyPatch, qapp: Any
) -> None:
    """数据页对话框路径：新建工作区与删除确认。."""
    from PySide2.QtWidgets import QMessageBox

    import finaldb.gui.widgets.pages.data_page as data_mod

    window, _theme, ws, *_rest = main_window
    data = _show(window, qapp, "data")

    # 新建对话框输入名称
    def fake_get_text(*_args: object, **_kwargs: object) -> tuple[str, bool]:
        """伪造输入对话框返回值。."""
        return "dialog-ws", True

    monkeypatch.setattr(data_mod.QInputDialog, "getText", staticmethod(fake_get_text))
    data._on_new_workspace()
    assert ws.current_workspace() == "dialog-ws"

    # 删除确认选「是」
    def fake_question(*_args: object, **_kwargs: object) -> object:
        """伪造确认对话框返回「是」。."""
        return QMessageBox.Yes

    monkeypatch.setattr(data_mod.QMessageBox, "question", staticmethod(fake_question))
    data._on_delete_workspace("dialog-ws")
    assert ws.current_workspace() == ""
    window.close()


def test_data_import_dialog_dispatches(main_window: WindowFixture, monkeypatch: pytest.MonkeyPatch, qapp: Any) -> None:
    """数据页导入对话框：选择文件后调用后台导入。."""
    import finaldb.gui.widgets.pages.data_page as data_mod

    window, _theme, ws, *_rest = main_window
    data = _show(window, qapp, "data")
    ws.create_workspace("imp-ws")

    calls: list[str] = []
    monkeypatch.setattr(ws, "import_file", calls.append)

    def fake_open_file(*_args: object, **_kwargs: object) -> tuple[str, str]:
        """伪造文件选择对话框返回 x.csv。."""
        return "x.csv", ""

    monkeypatch.setattr(data_mod.QFileDialog, "getOpenFileName", staticmethod(fake_open_file))
    data._on_import()
    assert calls == ["x.csv"]
    window.close()


def test_data_import_error_shows_toast(main_window: WindowFixture, tmp_path: Path, qapp: Any) -> None:
    """数据页导入失败经 error_raised 触发错误浮层。."""
    window, _theme, ws, *_rest = main_window
    data = _show(window, qapp, "data")
    ws.create_workspace("err-ws")

    errors: list[str] = []
    data._toast.show_message = lambda msg, is_error=False: errors.append((msg, is_error))  # type: ignore[method-assign]
    bad = _csv(tmp_path, "x.parquet", "junk")
    bad.write_bytes(b"junk")
    ws.import_file_sync(str(bad))
    assert errors and errors[0][1] is True
    window.close()


# ----------------------------- 数据清洗面板（数据页内嵌） -----------------------------


def test_clean_rule_flow(main_window: WindowFixture, tmp_path: Path, qapp: Any) -> None:
    """数据清洗面板联动：选表 → 选列 → 加规则 → 预览与应用可用。."""
    window, _theme, ws, clean_ctrl, *_rest = main_window
    data = _show(window, qapp, "data")
    clean = data._clean_pane

    ws.create_workspace("clean-bind")
    csv = _csv(tmp_path, "d.csv", "name,age\n 甲 ,30\n乙,\n")
    ws.import_file_sync(str(csv))
    qapp.processEvents()

    # 切到清洗模式触发面板 showEvent 重载
    data._mode_group.button(1).click()
    qapp.processEvents()
    assert clean._table_combo.count() == 1
    clean._on_table_activated(0)
    assert clean._current_table == "d"
    assert clean._column_combo.count() == 2
    clean._on_column_activated(0)
    assert clean._current_column == "name"

    # 默认规则类型为去首尾空白；无规则时按钮禁用
    assert not clean._preview_btn.isEnabled()
    clean._on_add_rule()
    assert clean_ctrl.rules_model().rowCount() == 1
    assert clean._rule_list.count() == 1
    assert clean._preview_btn.isEnabled()
    assert clean._apply_btn.isEnabled()

    # 预览填充模型并生成统计文本
    clean_ctrl.preview(ws.current_workspace_path(), "d")
    qapp.processEvents()
    assert clean_ctrl.preview_model().rowCount() == 2
    assert "读入行数" in clean_ctrl.report_text()
    assert clean._report_label.text() != ""

    # 同步落库到新表后重选工作区刷新表列表
    clean_ctrl.apply_sync(ws.current_workspace_path(), "d", "d_cleaned")
    ws.select_workspace(ws.current_workspace())
    assert ws.table_model().table_at(1) == "d_cleaned"
    window.close()


def test_clean_kind_params_visibility(main_window: WindowFixture, qapp: Any) -> None:
    """数据清洗面板参数区按规则类型显隐。."""
    window, *_rest = main_window
    data = _show(window, qapp, "data")
    clean = data._clean_pane

    # 默认 trim：参数区隐藏
    assert not clean._value_row.isVisibleTo(clean)
    assert not clean._replacement_row.isVisibleTo(clean)
    # 文本替换：查找与替换区可见
    clean._kind_combo.setCurrentIndex(3)
    assert clean._value_row.isVisibleTo(clean)
    assert clean._replacement_row.isVisibleTo(clean)
    # 缺失值填充：仅填充值可见
    clean._kind_combo.setCurrentIndex(5)
    assert clean._value_row.isVisibleTo(clean)
    assert not clean._replacement_row.isVisibleTo(clean)
    assert clean._value_label.text() == "填充值"
    window.close()


def test_clean_rule_row_remove(main_window: WindowFixture, qapp: Any) -> None:
    """数据清洗面板规则行内移除按钮回传行号。."""
    from PySide2.QtCore import Qt

    window, _theme, _ws, clean_ctrl, *_rest = main_window
    data = _show(window, qapp, "data")
    clean = data._clean_pane
    clean_ctrl.add_rule("trim", "name", "", "", "")
    clean_ctrl.add_rule("to_number", "age", "", "", "")
    qapp.processEvents()
    assert clean._rule_list.count() == 2

    # 移除首行规则
    clean._on_remove_rule(0)
    qapp.processEvents()
    assert clean_ctrl.rules_model().rowCount() == 1
    rule = clean_ctrl.rules_model().rule_at(0)
    assert rule is not None and rule.column == "age"
    # 越界静默
    clean._on_remove_rule(99)
    assert clean_ctrl.rules_model().rowCount() == 1
    # 角色数据兜底：清空后模型归零
    clean_ctrl.clear_rules()
    assert clean_ctrl.rules_model().data(clean_ctrl.rules_model().index(0, 0), Qt.UserRole + 1) is None
    window.close()


# ----------------------------- 合并去重面板（数据页内嵌） -----------------------------


def test_merge_three_modes_flow(main_window: WindowFixture, tmp_path: Path, qapp: Any) -> None:
    """合并去重面板三模式：union 多选 / dedup 键列 / join 四要素。."""
    window, _theme, ws, _clean, merge_ctrl, *_rest = main_window
    data = _show(window, qapp, "data")
    merge = data._merge_pane

    ws.create_workspace("merge-bind")
    csv = _csv(tmp_path, "d.csv", "name,age\n甲,30\n乙,25\n乙,25\n")
    ws.import_file_sync(str(csv))
    qapp.processEvents()

    # 切到合并模式触发面板 showEvent 重载
    data._mode_group.button(2).click()
    qapp.processEvents()

    # 模式 0：union 列表加载，单选不满足执行条件
    assert merge._union_list.count() == 1
    merge._on_union_item_clicked(merge._union_list.item(0))
    assert merge._union_tables == ["d"]
    assert not merge._apply_btn.isEnabled()

    # 模式 1：dedup 选表加载键列，执行可用
    merge._on_mode_changed(1)
    assert merge._stack.currentIndex() == 1
    merge._dedup_combo.setCurrentIndex(0)
    merge._on_dedup_table_activated(0)
    assert merge._dedup_table == "d"
    assert merge._dedup_list.count() == 2
    assert merge._apply_btn.isEnabled()
    # 键列点选维护顺序表
    merge._on_dedup_key_clicked(merge._dedup_list.item(0))
    assert merge._dedup_keys == ["name"]
    merge._on_dedup_key_clicked(merge._dedup_list.item(0))
    assert merge._dedup_keys == []

    # 同步去重落库
    merge_ctrl.apply_dedup_sync(ws.current_workspace_path(), "d", "name", "")
    merge._reload_tables()
    assert merge._union_list.count() == 2

    # 模式 0：两个表齐后执行可用（先清空早前阶段的选择）
    merge._on_mode_changed(0)
    merge._union_tables.clear()
    merge._on_union_item_clicked(merge._union_list.item(0))
    merge._on_union_item_clicked(merge._union_list.item(1))
    assert len(merge._union_tables) == 2
    assert merge._apply_btn.isEnabled()
    assert merge._union_count.text() == "已选 2 个表"

    # 模式 2：join 左右表与键列加载，四项齐后执行可用
    merge._on_mode_changed(2)
    merge._left_combo.setCurrentIndex(0)
    merge._right_combo.setCurrentIndex(1)
    merge._on_join_table_activated()
    assert merge._join_left == "d"
    assert merge._join_right == "d_dedup"
    assert merge._left_key_combo.count() == 2
    assert not merge._apply_btn.isEnabled()
    merge._set_join_key("name", is_left=True)
    merge._set_join_key("name", is_left=False)
    merge._set_join_how("left")
    assert merge._apply_btn.isEnabled()
    window.close()


# ----------------------------- 统计页 -----------------------------


def test_stats_page_summary_bars_and_columns(main_window: WindowFixture, tmp_path: Path, qapp: Any) -> None:
    """统计页联动：摘要、条形图与列统计表随导入刷新。."""
    window, _theme, ws, _clean, _merge, _edit, stats_ctrl, *_rest = main_window
    stats = _show(window, qapp, "stats")

    ws.create_workspace("stats-bind")
    csv = _csv(tmp_path, "s.csv", "name,age\n甲,30\n乙,25\n丙,\n")
    ws.import_file_sync(str(csv))
    qapp.processEvents()

    # showEvent 触发重载：摘要 + 条形图 + 表下拉
    window.set_current_page("data")
    stats = _show(window, qapp, "stats")
    assert stats._summary.text().startswith("共 1 张表")
    assert "3 行" in stats._summary.text()
    assert len(stats._bars) == 1
    assert stats._table_combo.count() == 1
    # 未选表时列统计空态
    assert not stats._stat_view.isVisible()
    assert stats._stat_view.model().rowCount() == 0

    # 选择表加载列统计（CSV 导入列为 TEXT：空值/唯一值正确，均值仅数值列计算）
    stats._on_table_activated(0)
    qapp.processEvents()
    model = stats_ctrl.table_stats_model()
    assert model.rowCount() == 2
    name_stat = model.stat_at(0)
    age_stat = model.stat_at(1)
    assert name_stat is not None and name_stat.name == "name"
    assert name_stat.null_count == 0 and name_stat.distinct_count == 3
    assert age_stat is not None and age_stat.null_count == 1
    assert age_stat.sql_type == "TEXT"
    assert age_stat.mean is None
    # 主题切换联动条形颜色
    window.sidebar._theme.set_dark(True)
    assert "#7AA2F7" in stats._bars[0].styleSheet()
    window.close()


# ----------------------------- 设置页 -----------------------------


def test_settings_controls_and_sync(main_window: WindowFixture, qapp: Any) -> None:
    """设置页控件：暗色开关与字号滑杆驱动主题并反向同步。."""
    window, theme, *_rest = main_window
    settings = _show(window, qapp, "settings")

    dark = settings._dark_check
    slider = settings._font_slider
    assert not dark.isChecked()
    assert slider.minimum() == 12 and slider.maximum() == 20

    # 控件 → 主题
    dark.setChecked(True)
    assert theme.is_dark() is True
    slider.setValue(16)
    assert theme.font_size_body() == 16

    # 主题 → 控件（模拟来自侧边栏开关的切换）
    theme.set_base_font_size(18)
    assert slider.value() == 18
    assert settings._font_label.text() == "18 px"
    window.close()


# ----------------------------- 关于页 -----------------------------


def test_about_page_badge_restyle(main_window: WindowFixture, qapp: Any) -> None:
    """关于页装配与「库」色块随主题刷新。."""
    window, theme, *_rest = main_window
    about = _show(window, qapp, "about")

    assert about._badge.text() == "库"
    assert "#0366D6" in about._badge.styleSheet()
    theme.set_dark(True)
    assert "#7AA2F7" in about._badge.styleSheet()
    window.close()
