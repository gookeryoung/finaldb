"""merge 门面：仅做 re-export。."""

from __future__ import annotations

from finaldb.core.merge.service import (
    JoinSpec,
    MergeJob,
    MergeSummary,
    dedup_table,
    join_tables,
    union_tables,
)

__all__ = ["JoinSpec", "MergeJob", "MergeSummary", "dedup_table", "join_tables", "union_tables"]
