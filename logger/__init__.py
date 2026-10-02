"""ByteLens run-record logging (root-level, first-class — Design Dungeons).

Every run writes one structured record (AGENTS.md section 8):
``run_id``, config hash, git SHA, seed, dataset split hash, model name,
metrics, wall time, hardware. Paper tables and figures are generated from
these records — never typed by hand. Records are JSON Lines (JSONL);
Parquet export lands in P1 with pandas/pyarrow.

No fabricated fields: anything unavailable (e.g. no git repo, no GPU) is
recorded as ``null``, never invented.
"""

from __future__ import annotations

from logger.run_records import (
    RunRecord,
    RunRecorder,
    append_jsonl,
    capture_env,
    config_hash,
    read_jsonl,
)

__all__ = [
    "RunRecord",
    "RunRecorder",
    "append_jsonl",
    "capture_env",
    "config_hash",
    "read_jsonl",
]
