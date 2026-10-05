"""ByteLens run-record logging (root-level, first-class — Design Dungeons).

Every run writes one structured record (AGENTS.md section 8): derived run ID,
config hash, git context, seed, dataset/split hashes, model name, metrics,
wall time, hardware, tags, test-window discipline, and a tamper-evident hash
chain (ADR-009). Paper tables and figures are generated from these records —
never typed by hand. Records are JSON Lines (JSONL); Parquet export lands in
P1 with pandas/pyarrow.

No fabricated fields: anything unavailable (e.g. no git repo, no GPU) is
recorded as ``null``, never invented.
"""

from __future__ import annotations

from logger.hashing import (
    canonical_json,
    hash_array,
    hash_config,
    hash_file,
    hash_object,
    hash_split_ids,
)
from logger.manifest import (
    ManifestError,
    dataset_hash,
    load_manifest,
    verify_data,
)
from logger.run_records import (
    SCHEMA_VERSION,
    RunRecord,
    RunRecorder,
    append_jsonl,
    capture_env,
    compute_record_hash,
    config_hash,
    derivable_run_id,
    expand_seeds,
    git_status,
    prepend_chain,
    prev_record_hash,
    read_jsonl,
    verify_chain,
)
from logger.splits import (
    SplitError,
    load_splits_lock,
    make_lock_entry,
    read_split_ids,
    split_hash,
    verify_all_splits,
    verify_split,
    write_split_ids,
    write_splits_lock,
)

__all__ = [
    # hashing (ADR-009)
    "canonical_json",
    "hash_array",
    "hash_config",
    "hash_file",
    "hash_object",
    "hash_split_ids",
    # manifest (ADR-009)
    "ManifestError",
    "dataset_hash",
    "load_manifest",
    "verify_data",
    # run records (ADR-007 + ADR-009)
    "SCHEMA_VERSION",
    "RunRecord",
    "RunRecorder",
    "append_jsonl",
    "capture_env",
    "compute_record_hash",
    "config_hash",
    "derivable_run_id",
    "expand_seeds",
    "git_status",
    "prepend_chain",
    "prev_record_hash",
    "read_jsonl",
    "verify_chain",
    # splits (ADR-009)
    "SplitError",
    "load_splits_lock",
    "make_lock_entry",
    "read_split_ids",
    "split_hash",
    "verify_all_splits",
    "verify_split",
    "write_split_ids",
    "write_splits_lock",
]
