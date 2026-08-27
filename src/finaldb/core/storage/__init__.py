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
from finaldb.core.storage.editing import (
    add_column,
    coerce_value,
    delete_rows,
    drop_column,
    fetch_rows,
    insert_row,
    rename_column,
    update_cell,
)

__all__ = [
    "ColumnInfo",
    "TableInfo",
    "add_column",
    "coerce_value",
    "connect",
    "create_table",
    "delete_rows",
    "drop_column",
    "drop_table",
    "fetch_preview",
    "fetch_rows",
    "find_free_table_name",
    "insert_row",
    "insert_rows",
    "quote_identifier",
    "rename_column",
    "table_exists",
    "table_infos",
    "table_names",
    "update_cell",
    "validate_identifier",
]
