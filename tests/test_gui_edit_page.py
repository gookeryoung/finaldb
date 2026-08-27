"""数据编辑页测试：表打开、单元格编辑、行列操作、撤销重做、分页。."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Tuple  # noqa: UP035  # 3.8 运行时下标兼容

import pytest

pytestmark = pytest.mark.gui

# main_window fixture 元组：(主窗口, 主题, 工作区/预览/清洗/合并/编辑/历史/统计/关于控制器)
WindowFixture = Tuple[Any, ...]  # noqa: UP006  # 3.8 运行时下标兼容


def _csv(tmp_path: Path, name: str, content: str) -> Path:
    """生成临时 CSV 文件。."""
    f = tmp_path / name
    f.write_text(content, "utf-8")
    return f


def _setup(main_window: WindowFixture, tmp_path: Path, qapp: Any, rows: str = "name,age\n甲,30\n乙,25\n") -> Any:
    """建工作区导入表并打开编辑页。."""
    window, _theme, ws, *_rest = main_window
    window.show()
    ws.create_workspace("edit-ws")
    ws.import_file_sync(str(_csv(tmp_path, "d.csv", rows)))
    qapp.processEvents()
    window.set_current_page("edit")
    qapp.processEvents()
    return window, window.pages["edit"]


# ----------------------------- 会话与单元格 -----------------------------


def test_open_table_and_edit_cell(main_window: WindowFixture, tmp_path: Path, qapp: Any) -> None:
    """打开表 → 编辑单元格 → 落库并支持撤销。."""
    window, *_rest = main_window
    page = _setup(main_window, tmp_path, qapp)[1]

    # 表下拉出现导入的表
    assert page._table_combo.count() == 1
    assert page._table_combo.itemText(0) == "d"
    assert not page._view.isVisible()

    page._on_table_activated(0)
    qapp.processEvents()
    assert page._edit.current_table() == "d"
    assert page._view.isVisible()
    assert page._edit.edit_model().rowCount() == 2

    # 编辑单元格（模型 setData 委托控制器落库）
    model = page._edit.edit_model()
    ok = model.setData(model.index(0, 1), "31")
    assert ok
    assert model.data(model.index(0, 1)) == "31"

    # 撤销恢复
    page._edit.undo()
    qapp.processEvents()
    model = page._edit.edit_model()
    assert model.data(model.index(0, 1)) == "30"
    window.close()


def test_edit_cell_bad_value_shows_error(main_window: WindowFixture, tmp_path: Path, qapp: Any) -> None:
    """INTEGER 列输入非法文本：编辑被拒并提示错误。."""
    window, *_theme_ws = main_window
    page = _setup(main_window, tmp_path, qapp)[1]
    page._on_table_activated(0)
    qapp.processEvents()

    errors: list[str] = []
    page._edit.error_raised.connect(errors.append)
    model = page._edit.edit_model()
    ok = model.setData(model.index(0, 1), "abc")
    assert not ok
    assert errors
    window.close()


# ----------------------------- 行列操作 -----------------------------


def test_row_and_column_operations(main_window: WindowFixture, tmp_path: Path, qapp: Any) -> None:
    """加行/删行/加列/重命名/删列全流程（含撤销）。."""
    window, *_rest = main_window
    page = _setup(main_window, tmp_path, qapp)[1]
    page._on_table_activated(0)
    qapp.processEvents()
    edit = page._edit

    # 加行
    edit.add_row()
    qapp.processEvents()
    assert edit.total_rows() == 3

    # 删行（选中第一行）
    view = page._view
    view.selectRow(0)
    rowids = edit.edit_model().rowids_of([0])
    assert len(rowids) == 1
    edit.delete_rows(rowids)
    qapp.processEvents()
    assert edit.total_rows() == 2

    # 撤销删行
    edit.undo()
    qapp.processEvents()
    assert edit.total_rows() == 3

    # 加列 + 重命名 + 删列
    edit.add_column("note")
    qapp.processEvents()
    assert edit.edit_model().columnCount() == 3
    edit.rename_column("note", "remark")
    qapp.processEvents()
    assert edit.edit_model().headerData(2, 0x1) == "remark"  # Qt.Horizontal
    edit.drop_column("remark")
    qapp.processEvents()
    assert edit.edit_model().columnCount() == 2
    edit.undo()
    qapp.processEvents()
    assert edit.edit_model().columnCount() == 3
    window.close()


def test_column_dialogs_dispatch(
    main_window: WindowFixture, tmp_path: Path, qapp: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    """加列/重命名对话框路径（monkeypatch 静态方法）。."""
    from PySide2.QtWidgets import QMessageBox

    import finaldb.gui.widgets.pages.edit_page as edit_mod

    window, *_rest = main_window
    page = _setup(main_window, tmp_path, qapp)[1]
    page._on_table_activated(0)
    qapp.processEvents()

    def fake_get_text(*_args: object, **_kwargs: object) -> tuple[str, bool]:
        """伪造输入对话框：新增列名 extra。."""
        return "extra", True

    monkeypatch.setattr(edit_mod.QInputDialog, "getText", staticmethod(fake_get_text))
    page._on_add_column()
    qapp.processEvents()
    assert page._edit.edit_model().columnCount() == 3

    # 选中 extra 列后重命名
    view = page._view
    view.setCurrentIndex(page._edit.edit_model().index(0, 2))

    def fake_rename_text(*_args: object, **_kwargs: object) -> tuple[str, bool]:
        """伪造输入对话框：重命名为 renamed。."""
        return "renamed", True

    monkeypatch.setattr(edit_mod.QInputDialog, "getText", staticmethod(fake_rename_text))
    page._on_rename_column()
    qapp.processEvents()
    assert page._edit.edit_model().headerData(2, 0x1) == "renamed"

    def fake_question(*_args: object, **_kwargs: object) -> object:
        """伪造确认对话框返回「是」。."""
        return QMessageBox.Yes

    # 确认删列
    monkeypatch.setattr(edit_mod.QMessageBox, "question", staticmethod(fake_question))
    page._on_drop_column()
    qapp.processEvents()
    assert page._edit.edit_model().columnCount() == 2
    window.close()


def test_delete_rows_requires_selection(main_window: WindowFixture, tmp_path: Path, qapp: Any) -> None:
    """未选中行点删行：提示不删除。"""
    window, *_rest = main_window
    page = _setup(main_window, tmp_path, qapp)[1]
    page._on_table_activated(0)
    qapp.processEvents()
    total_before = page._edit.total_rows()
    page._on_delete_rows()
    qapp.processEvents()
    assert page._edit.total_rows() == total_before
    window.close()


# ----------------------------- 分页 -----------------------------


def test_pagination(main_window: WindowFixture, tmp_path: Path, qapp: Any) -> None:
    """250 行数据分页：页码、上一页/下一页可用态。."""
    rows = "id\n" + "\n".join(str(i) for i in range(250)) + "\n"
    window, *_rest = main_window
    page = _setup(main_window, tmp_path, qapp, rows)[1]
    page._on_table_activated(0)
    qapp.processEvents()
    edit = page._edit

    assert edit.current_page() == 0
    assert edit.total_rows() == 250
    assert page._page_label.text().startswith("第 1/3 页")
    assert not page._prev_btn.isEnabled()
    assert page._next_btn.isEnabled()

    page._on_next_page()
    qapp.processEvents()
    assert edit.current_page() == 1
    assert page._prev_btn.isEnabled()
    # 第 2 页首行 id = 100
    model = edit.edit_model()
    assert model.data(model.index(0, 0)) == "100"

    # 跳过末页保护：goto_page(99) 钳制到第 3 页
    edit.goto_page(99)
    qapp.processEvents()
    assert edit.current_page() == 2
    assert not page._next_btn.isEnabled()
    window.close()


# ----------------------------- 清空表与复制 -----------------------------


def test_clear_table_confirm_and_undo(main_window: WindowFixture, tmp_path: Path, qapp: Any, monkeypatch: Any) -> None:
    """清空表：确认后表空且可撤销恢复；取消则不动。."""
    from PySide2.QtWidgets import QMessageBox

    import finaldb.gui.widgets.pages.edit_page as edit_mod

    window, *_rest = main_window
    page = _setup(main_window, tmp_path, qapp)[1]
    page._on_table_activated(0)
    qapp.processEvents()
    edit = page._edit
    total_before = edit.total_rows()

    # 未开表确认前：取消「否」不动
    def answer_no(*_a: object, **_k: object) -> int:
        return QMessageBox.No

    monkeypatch.setattr(edit_mod.QMessageBox, "question", staticmethod(answer_no))
    page._on_clear_table()
    qapp.processEvents()
    assert edit.total_rows() == total_before

    # 确认「是」：清空并可撤销全量恢复
    def answer_yes(*_a: object, **_k: object) -> int:
        return QMessageBox.Yes

    monkeypatch.setattr(edit_mod.QMessageBox, "question", staticmethod(answer_yes))
    page._on_clear_table()
    qapp.processEvents()
    assert edit.total_rows() == 0

    edit.undo()
    qapp.processEvents()
    assert edit.total_rows() == total_before
    window.close()


def test_copy_selection_tsv(main_window: WindowFixture, tmp_path: Path, qapp: Any) -> None:
    """Ctrl+C 复制选区为 TSV 文本。."""
    from PySide2.QtCore import QItemSelectionModel
    from PySide2.QtWidgets import QApplication

    window, *_rest = main_window
    page = _setup(main_window, tmp_path, qapp, "name,age\n甲,30\n乙,25\n")[1]
    page._on_table_activated(0)
    qapp.processEvents()

    model = page._edit.edit_model()
    # 选中 (0,0) 与 (1,1)（非矩形选区：补齐为 2x2 网格）
    view = page._view
    view.selectionModel().select(model.index(0, 0), QItemSelectionModel.Select)
    view.selectionModel().select(model.index(1, 1), QItemSelectionModel.Select)
    page._on_copy()
    text = QApplication.clipboard().text()
    assert "甲" in text and "25" in text
    assert text.count("\t") >= 1
    window.close()
