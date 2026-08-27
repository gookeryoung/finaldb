"""工作区控制器 / 导入 Worker / 模型测试。."""

from __future__ import annotations

import time
from pathlib import Path

import pytest
from PySide2.QtCore import Qt
from PySide2.QtGui import QGuiApplication

from finaldb.gui.controllers.workspace_controller import (
    WorkspaceController,
    _to_local_path,
    format_timestamp,
)
from finaldb.gui.workers.import_worker import ImportWorker

pytestmark = pytest.mark.gui


@pytest.fixture()
def ctrl(qapp: object, tmp_path: Path) -> WorkspaceController:
    """临时根目录的工作区控制器。."""
    return WorkspaceController(root=tmp_path / "ws")


def _csv(tmp_path: Path) -> Path:
    """生成两行 CSV。."""
    f = tmp_path / "demo.csv"
    f.write_text("a,b\n1,x\n2,y\n", "utf-8")
    return f


def test_initial_state(ctrl: WorkspaceController) -> None:
    """初始无工作区、无当前选择、不忙。."""
    assert ctrl.workspace_model().rowCount() == 0
    assert ctrl.current_workspace() == ""
    assert ctrl.current_workspace_path() == ""
    assert ctrl.is_busy() is False
    assert ctrl.table_model().rowCount() == 0


def test_create_workspace_selects_it(ctrl: WorkspaceController) -> None:
    """创建工作区后自动选中并刷新列表。."""
    ctrl.create_workspace("alpha")
    assert ctrl.current_workspace() == "alpha"
    assert ctrl.workspace_model().rowCount() == 1
    assert (Path(ctrl.current_workspace_path()) / "data.db").is_file()


def test_create_invalid_name_emits_error(ctrl: WorkspaceController) -> None:
    """非法名称经 error_raised 报错且不创建。."""
    errors: list[str] = []
    ctrl.error_raised.connect(errors.append)  # pyrefly: ignore [missing-attribute]
    ctrl.create_workspace("中文!!")
    assert errors and "无效" in errors[0]
    assert ctrl.workspace_model().rowCount() == 0


def test_select_and_delete_workspace(ctrl: WorkspaceController) -> None:
    """选择与删除工作区；删除当前工作区后自动切到剩余最近工作区。."""
    ctrl.create_workspace("alpha")
    ctrl.create_workspace("beta")
    ctrl.select_workspace("alpha")
    assert ctrl.current_workspace() == "alpha"
    ctrl.delete_workspace("alpha")
    # 剩余 beta：自动选中（刷新时无当前选择则取最近工作区）
    assert ctrl.current_workspace() == "beta"
    assert ctrl.workspace_model().rowCount() == 1
    # 删除最后一个工作区后清空选择
    ctrl.delete_workspace("beta")
    assert ctrl.current_workspace() == ""
    assert ctrl.workspace_model().rowCount() == 0


def test_refresh_auto_selects_latest_workspace(qapp: object, tmp_path: Path) -> None:
    """启动（refresh）时无当前选择则自动选中最近工作区并载入表列表。."""
    root = tmp_path / "ws"
    boot = WorkspaceController(root=root)
    boot.create_workspace("alpha")
    boot.import_file_sync(str(_csv(tmp_path)))
    assert boot.table_model().rowCount() == 1

    # 模拟重启：新控制器扫描同一根目录，无需手动选择即载入
    restarted = WorkspaceController(root=root)
    assert restarted.current_workspace() == "alpha"
    assert restarted.table_model().rowCount() == 1
    name = restarted.table_model().table_at(0)
    assert name is not None and name == "demo"


def test_delete_missing_workspace_emits_error(ctrl: WorkspaceController) -> None:
    """删除不存在的工作区报错。."""
    errors: list[str] = []
    ctrl.error_raised.connect(errors.append)  # pyrefly: ignore [missing-attribute]
    ctrl.delete_workspace("ghost")
    assert errors and "不存在" in errors[0]


def test_select_missing_workspace_emits_error(ctrl: WorkspaceController) -> None:
    """选择不存在的工作区报错。."""
    errors: list[str] = []
    ctrl.error_raised.connect(errors.append)  # pyrefly: ignore [missing-attribute]
    ctrl.select_workspace("ghost")
    assert errors and "不存在" in errors[0]


def test_import_file_sync_updates_tables(ctrl: WorkspaceController, tmp_path: Path) -> None:
    """同步导入后表列表刷新且 import_finished 发信号。."""
    ctrl.create_workspace("alpha")
    messages: list[str] = []
    ctrl.import_finished.connect(messages.append)  # pyrefly: ignore [missing-attribute]
    ctrl.import_file_sync(str(_csv(tmp_path)))
    assert messages and "demo(2 行)" in messages[0]
    assert ctrl.table_model().rowCount() == 1
    assert ctrl.table_model().table_at(0) == "demo"


def test_import_without_workspace_emits_error(ctrl: WorkspaceController, tmp_path: Path) -> None:
    """未选工作区导入报错。."""
    errors: list[str] = []
    ctrl.error_raised.connect(errors.append)  # pyrefly: ignore [missing-attribute]
    ctrl.import_file_sync(str(_csv(tmp_path)))
    assert errors and "先选择工作区" in errors[0]


def test_import_bad_format_emits_failure(ctrl: WorkspaceController, tmp_path: Path) -> None:
    """不支持的文件格式经 import_failed 报错。."""
    ctrl.create_workspace("alpha")
    f = tmp_path / "x.parquet"
    f.write_bytes(b"junk")
    failures: list[str] = []
    ctrl.import_failed.connect(failures.append)  # pyrefly: ignore [missing-attribute]
    ctrl.import_file_sync(str(f))
    assert failures and "导入失败" in failures[0]


def test_import_file_async_thread(qapp: object, ctrl: WorkspaceController, tmp_path: Path) -> None:
    """后台线程导入完成后列表刷新且忙状态复位。."""
    ctrl.create_workspace("alpha")
    messages: list[str] = []
    ctrl.import_finished.connect(messages.append)  # pyrefly: ignore [missing-attribute]
    ctrl.import_file(str(_csv(tmp_path)))
    assert ctrl.is_busy() is True
    deadline = time.monotonic() + 10.0
    while not messages and time.monotonic() < deadline:
        QGuiApplication.processEvents()
        time.sleep(0.02)
    assert messages, "后台导入未在超时前完成"
    assert "demo(2 行)" in messages[0]
    # 线程退出后忙状态复位
    deadline = time.monotonic() + 5.0
    while ctrl.is_busy() and time.monotonic() < deadline:
        QGuiApplication.processEvents()
        time.sleep(0.02)
    assert ctrl.is_busy() is False
    assert ctrl.table_model().rowCount() == 1


def test_import_async_without_workspace(qapp: object, ctrl: WorkspaceController) -> None:
    """无工作区时后台导入入口同样报错。."""
    errors: list[str] = []
    ctrl.error_raised.connect(errors.append)  # pyrefly: ignore [missing-attribute]
    ctrl.import_file("whatever.csv")
    assert errors and "先选择工作区" in errors[0]


def test_to_local_path_variants() -> None:
    """file:/// URL 与普通路径的本地路径解析。."""
    assert _to_local_path("file:///C:/data/a.csv") == "C:/data/a.csv"
    assert _to_local_path("file://") == ""
    assert _to_local_path("") == ""
    assert _to_local_path("  ") == ""
    assert _to_local_path("/tmp/x.csv") == "/tmp/x.csv"


def test_format_timestamp() -> None:
    """时间戳格式化：无效值显示占位符。."""
    assert format_timestamp(0) == "—"
    assert len(format_timestamp(1700000000)) == 16


def test_import_worker_success_and_failure(tmp_path: Path) -> None:
    """Worker 直接调用：成功发 finished，失败发 failed。."""
    ws_db = tmp_path / "data.db"
    import sqlite3

    conn = sqlite3.connect(str(ws_db))
    conn.close()
    ok: list[str] = []
    bad: list[str] = []
    w_ok = ImportWorker(str(ws_db), str(_csv(tmp_path)))
    w_ok.finished.connect(ok.append)  # pyrefly: ignore [missing-attribute]
    w_ok.failed.connect(bad.append)  # pyrefly: ignore [missing-attribute]
    w_ok.run()
    assert ok and bad == []
    conn = sqlite3.connect(str(ws_db))
    cur = conn.execute("SELECT COUNT(*) FROM demo")
    assert cur.fetchone()[0] == 2
    conn.close()
    # 失败路径：不支持格式
    junk = tmp_path / "x.parquet"
    junk.write_bytes(b"j")
    w_bad = ImportWorker(str(ws_db), str(junk))
    w_bad.finished.connect(ok.append)  # pyrefly: ignore [missing-attribute]
    w_bad.failed.connect(bad.append)  # pyrefly: ignore [missing-attribute]
    w_bad.run()
    assert bad and "导入失败" in bad[0]


def test_workspace_model_data_roles(ctrl: WorkspaceController) -> None:
    """WorkspaceListModel 角色数据与边界行为。."""
    ctrl.create_workspace("alpha")
    from finaldb.core.workspace import WorkspaceMeta

    metas = [WorkspaceMeta("beta", Path("/tmp/beta"), 3, 30, 1700000000.0)]
    ctrl.workspace_model().reload(metas)
    assert ctrl.workspace_model().rowCount() == 1
    idx = ctrl.workspace_model().index(0, 0)
    assert ctrl.workspace_model().data(idx, Qt.UserRole + 1) == "beta"
    assert ctrl.workspace_model().data(idx, Qt.UserRole + 2) == 3
    assert ctrl.workspace_model().data(idx, Qt.UserRole + 3) == 30
    assert ctrl.workspace_model().data(idx, Qt.UserRole + 4) == format_timestamp(1700000000.0)
    assert ctrl.workspace_model().data(idx, Qt.UserRole + 5) == str(Path("/tmp/beta"))
    # 越界与无效角色返回 None
    assert ctrl.workspace_model().data(ctrl.workspace_model().index(5, 0), Qt.UserRole + 1) is None
    assert ctrl.workspace_model().data(idx, Qt.DisplayRole) is None
    assert ctrl.workspace_model().meta_at(0) is metas[0]
    assert ctrl.workspace_model().meta_at(9) is None
    ctrl.workspace_model().clear()
    assert ctrl.workspace_model().rowCount() == 0


def test_table_list_model_edges(qapp: object) -> None:
    """TableListModel 边界：空模型、无效索引、未知角色。."""
    from finaldb.gui.models.table_model import TableListModel

    tl = TableListModel()
    assert tl.rowCount() == 0
    assert tl.table_at(0) is None
    assert tl.data(tl.index(0, 0), Qt.UserRole + 1) is None
    tl.reload([("t", 5)])
    assert tl.data(tl.index(0, 0), Qt.UserRole + 2) == 5
    assert tl.data(tl.index(0, 0), Qt.UserRole + 9) is None
