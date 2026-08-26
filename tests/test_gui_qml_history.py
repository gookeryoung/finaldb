"""HistoryPage QML 冒烟测试：页面加载、快照列表联动、同步对比与回滚。."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from PySide2.QtGui import QGuiApplication
from PySide2.QtQuick import QQuickItem

from tests.conftest import find_sidebar, qml_set_prop

pytestmark = pytest.mark.gui

# qml_engine fixture 元组：(引擎, 主题, 根窗口, 工作区/预览/清洗/合并/历史控制器)
QmlFixture = tuple[Any, Any, Any, Any, Any, Any, Any, Any]


def test_historypage_loads(qml_engine: QmlFixture) -> None:
    """切换到版本历史页后 HistoryPage 成功创建。."""
    _engine, _theme, root, *_rest = qml_engine
    sidebar = find_sidebar(root)
    qml_set_prop(sidebar, "currentPage", "history")
    QGuiApplication.processEvents()
    history_page = root.findChild(QQuickItem, "historyPage")
    assert history_page is not None, "HistoryPage 未加载"
    qml_set_prop(sidebar, "currentPage", "home")
    QGuiApplication.processEvents()


def test_historypage_snapshots_diff_restore(qml_engine: QmlFixture, tmp_path: Path) -> None:
    """工作区导入两次后 HistoryPage 联动：快照列表 → 同步对比 → 同步回滚。."""
    _engine, _theme, root, ws, _pv, _cl, _mg, hist, *_rest = qml_engine
    # 准备工作区与两次导入（每次导入自动打快照）
    ws.create_workspace("hist-bind")
    csv1 = tmp_path / "a.csv"
    csv1.write_text("name,age\n甲,30\n乙,25\n", "utf-8")
    ws.import_file_sync(str(csv1))
    QGuiApplication.processEvents()

    sidebar = find_sidebar(root)
    qml_set_prop(sidebar, "currentPage", "history")
    QGuiApplication.processEvents()

    workspace_path = ws.currentWorkspacePath
    hist.load_history(workspace_path)
    assert hist.snapshotsModel.rowCount() == 1
    first = hist.snapshotsModel.snapshot_at(0)
    assert first is not None and first.message == "导入 a.csv"

    csv2 = tmp_path / "b.csv"
    csv2.write_text("name,age\n丙,40\n", "utf-8")
    ws.import_file_sync(str(csv2))
    QGuiApplication.processEvents()
    hist.load_history(workspace_path)
    assert hist.snapshotsModel.rowCount() == 2

    # 同步对比：首 → 最新（新增表 b）
    second = hist.snapshotsModel.snapshot_at(0)
    assert second is not None
    hist.diff_sync(workspace_path, first.short_id, second.short_id)
    QGuiApplication.processEvents()
    assert "表 a" in hist.diffText
    assert "表 b" in hist.diffText

    # 同步回滚到首个快照：表 b 消失
    hist.restore_sync(workspace_path, first.short_id)
    QGuiApplication.processEvents()
    from finaldb.core.storage.database import connect, table_exists

    conn = connect(Path(workspace_path) / "data.db")
    try:
        assert table_exists(conn, "a")
        assert not table_exists(conn, "b")
    finally:
        conn.close()

    qml_set_prop(sidebar, "currentPage", "home")
    QGuiApplication.processEvents()
