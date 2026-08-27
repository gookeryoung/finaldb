"""样例数据文件测试：tests/data 下全部格式均可解析落库，防止样例腐化。."""

from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from pathlib import Path

import pytest

from finaldb.core.importers.service import import_into_workspace

DATA_DIR = Path(__file__).parent / "data"

# 样例清单：(文件名, 落库表名, 数据行数)
_SAMPLES = [
    ("employees.csv", "employees", 7),
    ("employees.xlsx", "employees_roster", 7),
    ("employees.json", "employees", 7),
    ("departments.csv", "departments", 4),
    ("orders.ndjson", "orders", 5),
    ("products.tsv", "products", 5),
]


@pytest.fixture()
def conn(tmp_path: Path) -> Iterator[sqlite3.Connection]:
    """临时数据库连接。."""
    c = sqlite3.connect(str(tmp_path / "ws.db"))
    yield c
    c.close()


@pytest.mark.parametrize(("filename", "table", "rows"), _SAMPLES)
def test_sample_imports_into_workspace(conn: sqlite3.Connection, filename: str, table: str, rows: int) -> None:
    """每种格式的样例文件都能导入落库且行数一致。."""
    results = import_into_workspace(conn, DATA_DIR / filename)
    assert len(results) == 1
    assert results[0].table == table
    assert results[0].rows == rows
    assert results[0].source == filename


def test_employee_samples_share_schema(conn: sqlite3.Connection) -> None:
    """同一份员工名单的三种格式样例列名与行数一致。."""
    for filename in ("employees.csv", "employees.xlsx", "employees.json"):
        import_into_workspace(conn, DATA_DIR / filename)
    names = [row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")]
    employee_tables = [n for n in names if n.startswith("employees")]
    assert len(employee_tables) == 3
    column_sets = {tuple(row[1] for row in conn.execute(f'PRAGMA table_info("{t}")')) for t in employee_tables}
    assert column_sets == {("name", "age", "city", "salary")}
    for table in employee_tables:
        count = conn.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()
        assert count is not None and count[0] == 7
