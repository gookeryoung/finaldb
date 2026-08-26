"""storage 门面：仅做 re-export。."""

from __future__ import annotations

from finaldb.core.storage.database import (
    ColumnInfo,
    TableInfo,
    connect,
    create_table,
    drop_table,
    fetch_preview,
    find_free_table_name,
    insert_rows,
    quote_identifier,
    table_exists,
    table_infos,
    table_names,
    validate_identifier,
)

__all__ = [
    "ColumnInfo",
    "TableInfo",
    "connect",
    "create_table",
    "drop_table",
    "fetch_preview",
    "find_free_table_name",
    "insert_rows",
    "quote_identifier",
    "table_exists",
    "table_infos",
    "table_names",
    "validate_identifier",
]
