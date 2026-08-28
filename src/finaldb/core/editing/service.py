"""编辑服务：命令化即时落库 + 多级撤销/重做。

每条编辑命令立即写库，同时记录正向参数（重做用）与逆操作参数（撤销用）；
撤销/重做同样即时落库，配合快照（versioning）提供整体回滚兜底。
行级操作以 rowid 定位；删行的撤销按原 rowid 复活，删列的撤销恢复整列数据。
"""

from __future__ import annotations

import sqlite3
from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import cast

from finaldb.core.storage.database import column_infos, connect, row_count_of
from finaldb.core.storage.editing import (
    add_column as _add_column,
)
from finaldb.core.storage.editing import (
    coerce_value as _coerce_value,
)
from finaldb.core.storage.editing import (
    delete_rows as _delete_rows,
)
from finaldb.core.storage.editing import (
    drop_column as _drop_column,
)
from finaldb.core.storage.editing import (
    fetch_rows as _fetch_rows,
)
from finaldb.core.storage.editing import (
    insert_row as _insert_row,
)
from finaldb.core.storage.editing import (
    move_column as _move_column,
)
from finaldb.core.storage.editing import (
    rename_column as _rename_column,
)
from finaldb.core.storage.editing import (
    revive_row as _revive_row,
)
from finaldb.core.storage.editing import (
    update_cell as _update_cell,
)
from finaldb.core.storage.keys import (
    clear_key_rule as _clear_key_rule,
)
from finaldb.core.storage.keys import (
    get_key_rule as _get_key_rule,
)
from finaldb.core.storage.keys import (
    next_key as _next_key,
)
from finaldb.core.storage.keys import (
    set_key_rule as _set_key_rule,
)

__all__ = ["EditCommand", "EditService"]

# 撤销栈深度上限
_MAX_UNDO = 100

# 每页行数（编辑页分页）
PAGE_SIZE = 100


@dataclass(frozen=True)
class EditCommand:
    """一条编辑命令：正向参数 + 逆操作参数。

    :ivar op: 操作类型（set_cell/insert_row/delete_rows/add_column/rename_column/drop_column/clear_table）
    :ivar label: 人读描述（如「修改 t.age」）
    :ivar args: 正向参数（重做时按 _apply_forward 约定执行）
    :ivar undo_args: 逆操作参数（撤销时按 _apply_inverse 约定执行）
    """

    op: str
    label: str
    args: tuple[object, ...] = field(default=())
    undo_args: tuple[object, ...] = field(default=())


class EditService:
    """工作区数据编辑服务（每命令短连接，撤销栈内存维护）。."""

    def __init__(self, db_path: Path) -> None:
        """初始化服务。

        :param db_path: 工作区 data.db 路径
        """
        self._db_path = db_path
        self._undo: list[EditCommand] = []
        self._redo: list[EditCommand] = []

    # ----------------------------- 查询 -----------------------------

    def can_undo(self) -> bool:
        """是否有可撤销命令。."""
        return bool(self._undo)

    def can_redo(self) -> bool:
        """是否有可重做命令。."""
        return bool(self._redo)

    def undo_label(self) -> str:
        """撤销栈顶命令描述（空栈为空串）。."""
        return self._undo[-1].label if self._undo else ""

    def redo_label(self) -> str:
        """重做栈顶命令描述（空栈为空串）。."""
        return self._redo[-1].label if self._redo else ""

    def fetch_page(self, table: str, page: int) -> tuple[list[str], list[tuple[int, tuple[object, ...]]], int]:
        """读取指定页数据。

        :param table: 表名
        :param page: 页码（0 起）
        :return: (列名列表, [(rowid, 行值元组), ...], 总行数)
        """
        with self._session() as conn:
            names, rows = _fetch_rows(conn, table, offset=page * PAGE_SIZE, limit=PAGE_SIZE)
            return names, rows, row_count_of(conn, table)

    # ----------------------------- 编辑命令（即时落库 + 登记撤销） -----------------------------

    def set_cell(self, table: str, rowid: int, column: str, text: str) -> None:
        """修改单元格（按列类型转换输入文本）。

        :param table: 表名
        :param rowid: 行标识
        :param column: 列名
        :param text: 界面输入文本（空串置 NULL）
        :raises ValueError: 列/行不存在、文本无法按列类型转换、新旧值相同
        """
        with self._session() as conn:
            sql_type = self._column_type(conn, table, column)
            old = conn.execute(f'SELECT "{column}" FROM "{table}" WHERE rowid = ?', (rowid,)).fetchone()
            if old is None:
                raise ValueError(f"行不存在: {table}#{rowid}")
            try:
                new = _coerce_value(sql_type, text)
            except ValueError as exc:
                raise ValueError(f"{table}.{column} 输入不符合 {sql_type} 类型: {exc}") from exc
            if new == old[0]:
                return
            _update_cell(conn, table, rowid, column, new)
        self._push(
            EditCommand(
                op="set_cell",
                label=f"修改 {table}.{column}",
                args=(table, rowid, column, new),
                undo_args=(table, rowid, column, old[0]),
            )
        )

    def add_row(self, table: str, values: Sequence[object] | None = None) -> int:
        """追加一行（缺省全 NULL；已定义键规则时自动生成键序号），返回新行 rowid。"""
        with self._session() as conn:
            names = [c.name for c in column_infos(conn, table)]
            row: list[object] = list(values) if values is not None else [None] * len(names)
            if values is None:
                # 键规则：在键列自动填入下一序号
                rule = _get_key_rule(conn, table)
                if rule is not None and rule[0] in names:
                    key = _next_key(conn, table, rule[0])
                    if key is not None:
                        row[names.index(rule[0])] = key
            rowid = _insert_row(conn, table, row)
        self._push(
            EditCommand(
                op="insert_row",
                label=f"在 {table} 追加行",
                args=(table, rowid, tuple(row)),
                undo_args=(table, (rowid,)),
            )
        )
        return rowid

    def delete_rows(self, table: str, rowids: Sequence[int]) -> None:
        """删除行（登记整行快照供撤销复活）。"""
        if not rowids:
            return
        with self._session() as conn:
            names = [c.name for c in column_infos(conn, table)]
            col_sql = ", ".join(f'"{c}"' for c in names)
            placeholders = ", ".join("?" for _ in rowids)
            snapshots = conn.execute(
                f'SELECT rowid, {col_sql} FROM "{table}" WHERE rowid IN ({placeholders})',
                tuple(rowids),
            ).fetchall()
            _delete_rows(conn, table, rowids)
        self._push(
            EditCommand(
                op="delete_rows",
                label=f"删除 {table} 的 {len(snapshots)} 行",
                args=(table, tuple(rowids)),
                undo_args=(table, tuple((int(r[0]), tuple(r[1:])) for r in snapshots)),
            )
        )

    def add_column(self, table: str, column: str, sql_type: str = "TEXT") -> None:
        """追加新列。"""
        with self._session() as conn:
            _add_column(conn, table, column, sql_type)
        self._push(
            EditCommand(
                op="add_column",
                label=f"在 {table} 新增列 {column}",
                args=(table, column, sql_type),
                undo_args=(table, column),
            )
        )

    def rename_column(self, table: str, old: str, new: str) -> None:
        """重命名列。"""
        with self._session() as conn:
            _rename_column(conn, table, old, new)
        self._push(
            EditCommand(
                op="rename_column",
                label=f"重命名 {table}.{old} 为 {new}",
                args=(table, old, new),
                undo_args=(table, new, old),
            )
        )

    def drop_column(self, table: str, column: str) -> None:
        """删除列（登记整列数据与原位置供撤销恢复）。"""
        with self._session() as conn:
            sql_type = self._column_type(conn, table, column)
            position = [c.name for c in column_infos(conn, table)].index(column)
            data = conn.execute(f'SELECT rowid, "{column}" FROM "{table}"').fetchall()
            _drop_column(conn, table, column)
        self._push(
            EditCommand(
                op="drop_column",
                label=f"删除 {table}.{column}",
                args=(table, column),
                undo_args=(table, column, sql_type, position, tuple((int(r[0]), r[1]) for r in data)),
            )
        )

    def clear_table(self, table: str) -> None:
        """清空表全部行（登记整表快照供撤销按原 rowid 复活）。"""
        with self._session() as conn:
            names = [c.name for c in column_infos(conn, table)]
            col_sql = ", ".join(f'"{c}"' for c in names)
            snapshots = conn.execute(f'SELECT rowid, {col_sql} FROM "{table}"').fetchall()
            _delete_rows(conn, table, [int(r[0]) for r in snapshots])
        self._push(
            EditCommand(
                op="clear_table",
                label=f"清空 {table}（{len(snapshots)} 行）",
                args=(table,),
                undo_args=(table, tuple((int(r[0]), tuple(r[1:])) for r in snapshots)),
            )
        )

    # ----------------------------- 键规则 -----------------------------

    def key_rule(self, table: str) -> tuple[str, int] | None:
        """读取表的键规则。

        :param table: 表名
        :return: (键列名, 下一序号)；未定义返回 None
        """
        with self._session() as conn:
            return _get_key_rule(conn, table)

    def set_key_rule(self, table: str, column: str, start: int) -> None:
        """定义表的键规则（起始序号与现有数据取较大者）。

        :param table: 表名
        :param column: 键列名（须存在）
        :param start: 起始序号
        :raises ValueError: 列不存在
        """
        with self._session() as conn:
            self._column_type(conn, table, column)
            _set_key_rule(conn, table, column, start)

    def clear_key_rule(self, table: str) -> None:
        """清除表的键规则。."""
        with self._session() as conn:
            _clear_key_rule(conn, table)

    # ----------------------------- 撤销 / 重做 -----------------------------

    def undo(self) -> None:
        """撤销栈顶命令（即时落库并入重做栈）。

        :raises ValueError: 栈为空
        """
        if not self._undo:
            raise ValueError("无可撤销操作")
        cmd = self._undo.pop()
        with self._session() as conn:
            self._apply_inverse(conn, cmd)
        self._redo.append(cmd)

    def redo(self) -> None:
        """重做栈顶命令（即时落库并入撤销栈）。

        :raises ValueError: 栈为空
        """
        if not self._redo:
            raise ValueError("无可重做操作")
        cmd = self._redo.pop()
        with self._session() as conn:
            self._apply_forward(conn, cmd)
        self._undo.append(cmd)

    # ----------------------------- 内部 -----------------------------

    @contextmanager
    def _session(self) -> Iterator[sqlite3.Connection]:
        """短连接会话（确保关闭，注意 sqlite3 连接的 with 是事务语义不关闭）。."""
        conn = connect(self._db_path)
        try:
            yield conn
        finally:
            conn.close()

    @staticmethod
    def _column_type(conn: sqlite3.Connection, table: str, column: str) -> str:
        """查列类型（列不存在抛 ValueError）。."""
        for info in column_infos(conn, table):
            if info.name == column:
                return info.sql_type
        raise ValueError(f"列不存在: {table}.{column}")

    def _push(self, cmd: EditCommand) -> None:
        """命令入撤销栈（清空重做栈，超限淘汰栈底）。"""
        self._undo.append(cmd)
        if len(self._undo) > _MAX_UNDO:
            self._undo.pop(0)
        self._redo.clear()

    @staticmethod
    def _apply_forward(conn: sqlite3.Connection, cmd: EditCommand) -> None:
        """重做：按原命令正向参数重新执行。."""
        args = cmd.args
        table = args[0]
        if cmd.op == "set_cell":
            _update_cell(conn, table, args[1], args[2], args[3])
        elif cmd.op == "insert_row":
            # 撤销时该行已按 rowid 删除，重做按原 rowid 复活
            _revive_row(conn, table, args[1], args[2])
        elif cmd.op == "delete_rows":
            _delete_rows(conn, table, args[1])
        elif cmd.op == "add_column":
            _add_column(conn, table, args[1], args[2])
        elif cmd.op == "rename_column":
            _rename_column(conn, table, args[1], args[2])
        elif cmd.op == "drop_column":
            _drop_column(conn, table, args[1])
        elif cmd.op == "clear_table":
            # 重做：删除清空后新写入的全部行（再次清空）
            rowids = [int(r[0]) for r in conn.execute(f'SELECT rowid FROM "{table}"').fetchall()]
            _delete_rows(conn, table, rowids)
        else:  # pragma: no cover - 未知命令类型
            raise ValueError(f"未知命令: {cmd.op}")

    @staticmethod
    def _apply_inverse(conn: sqlite3.Connection, cmd: EditCommand) -> None:
        """撤销：按逆操作参数执行。."""
        args = cmd.undo_args
        table = args[0]
        if cmd.op == "set_cell":
            _update_cell(conn, table, args[1], args[2], args[3])
        elif cmd.op == "insert_row":
            _delete_rows(conn, table, args[1])
        elif cmd.op in {"delete_rows", "clear_table"}:
            # cast 首参在运行时求值，3.8 无内置泛型下标，用字符串前向引用
            for rowid, values in cast("tuple[tuple[int, tuple[object, ...]], ...]", args[1]):
                _revive_row(conn, table, rowid, values)
        elif cmd.op == "add_column":
            _drop_column(conn, table, args[1])
        elif cmd.op == "rename_column":
            _rename_column(conn, table, args[1], args[2])
        elif cmd.op == "drop_column":
            _, column, sql_type, position, data = args
            _add_column(conn, table, column, sql_type)
            for rowid, value in cast("tuple[tuple[int, object], ...]", data):
                _update_cell(conn, table, rowid, column, value)
            # 恢复列的原始次序（add_column 只能追加到末尾）
            _move_column(conn, table, column, position)
        else:  # pragma: no cover - 未知命令类型
            raise ValueError(f"未知命令: {cmd.op}")
