"""``python -m logger.trace <artifact-id | run_id>`` (ADR-009).

Prints the full provenance chain for a paper table cell: the artifact (when
given an artifact id), every run behind it, and — for each run — the exact
config, data/split hashes, code state, environment, seeds, and the one
command that reproduces it.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

from logger.run_records import RunRecord, read_jsonl

RECORDS_PATH = Path("logger/runs.jsonl")
ARTIFACTS_DIR = Path("paper/artifacts")


def find_run(run_id: str, records_path: str | Path | None = None) -> RunRecord:
    """Locate a run by ID across all records; raise SystemExit when absent."""
    p = Path(RECORDS_PATH if records_path is None else records_path)
    if not p.is_file():
        print(f"no run records found at {p}", file=sys.stderr)
        raise SystemExit(1)
    for rec in read_jsonl(p):
        if rec.run_id == run_id:
            return rec
    print(f"run_id {run_id!r} not found in {p}", file=sys.stderr)
    raise SystemExit(1)


def load_artifact(artifact_id: str, artifacts_dir: str | Path | None = None) -> dict[str, Any]:
    """Load ``paper/artifacts/<id>.json``; raise SystemExit when absent."""
    d = Path(ARTIFACTS_DIR if artifacts_dir is None else artifacts_dir)
    p = d / f"{artifact_id}.json"
    if not p.is_file():
        print(f"artifact {artifact_id!r} not found at {p}", file=sys.stderr)
        raise SystemExit(1)
    return json.loads(p.read_text(encoding="utf-8"))


def reproduction_command(rec: RunRecord) -> str:
    """The exact command that reproduces a run from its record."""
    return f"python -m logger.repro {rec.run_id}"


def format_run(rec: RunRecord) -> list[str]:
    """Human-readable provenance lines for one run record."""
    lines = [
        f"run_id        : {rec.run_id}",
        f"created       : {rec.created}",
        f"model         : {rec.model_name}",
        f"seed(s)       : python={rec.seeds['python'] if rec.seeds else rec.seed} "
        f"numpy={rec.seeds['numpy'] if rec.seeds else rec.seed} "
        f"framework={rec.seeds['framework'] if rec.seeds else rec.seed}",
        f"tags          : {rec.tags or []}",
        f"test_touched  : {rec.test_touched} (lock: {rec.test_lock_hash})",
        "",
        "config:",
        json.dumps(rec.config, indent=2, sort_keys=True),
        f"config_hash   : {rec.config_hash}",
        "",
        "data & split:",
        f"dataset_hash  : {rec.dataset_hash}",
        f"split_name    : {rec.split_name}",
        f"split_hash    : {rec.dataset_split_hash}",
        "",
        "code & environment:",
        f"git_sha       : {rec.git_sha} (branch {rec.branch}, dirty={rec.git_dirty}, "
        f"diff_hash={rec.git_diff_hash})",
        f"python        : {rec.hardware.get('python')}",
        f"requirements  : {rec.requirements_hash}",
        f"sandbox_image : {rec.hardware.get('sandbox_image')}",
        f"determinism   : {rec.determinism}",
        "",
        "result:",
        f"metrics       : {rec.metrics}",
        f"wall_time_sec : {rec.wall_time_sec}",
        f"record_hash   : {rec.record_hash}",
        f"prev_record   : {rec.prev_record_hash}",
        "",
        f"reproduce     : {reproduction_command(rec)}",
    ]
    return lines


def main(argv: list[str] | None = None) -> int:
    """Trace an artifact id or run_id; prints the chain and reproduction command."""
    args = list(sys.argv[1:] if argv is None else argv)
    if len(args) != 1:
        print("usage: python -m logger.trace <artifact-id | run_id>", file=sys.stderr)
        return 2
    target = args[0]

    artifact_path = Path(ARTIFACTS_DIR) / f"{target}.json"
    if artifact_path.is_file():
        artifact = load_artifact(target)
        print(f"artifact      : {artifact['table_id']}")
        print(f"output_sha256 : {artifact['output_sha256']}")
        print(f"generator_sha : {artifact.get('generator_git_sha')}")
        print(f"runs          : {artifact['run_ids']}")
        print("=" * 60)
        for rid in artifact["run_ids"]:
            rec = find_run(rid)
            print("\n".join(format_run(rec)))
            print("-" * 60)
        return 0

    rec = find_run(target)
    print("\n".join(format_run(rec)))
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
