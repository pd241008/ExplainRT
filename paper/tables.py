"""Paper table generation from run records (ADR-009; AGENTS.md §8).

Generators read **only** run records and emit a traceable artifact:

- ``paper/artifacts/<id>.json`` — the run_ids used, every hash in the chain
  (config/dataset/split/record hashes), the generator's git SHA, and the
  artifact's own output sha256
- ``paper/build_manifest.json`` — one entry per artifact, appended per build

Refusal rules (the point of the module — enforced before any number is
aggregated):

- refuse runs tagged ``smoke`` or ``pilot-10pct`` (dev scaffolding, never in
  paper tables);
- refuse any run with ``test_touched=True`` unless its ``test_lock_hash``
  matches a freeze lock in ``configs/frozen/``;
- records failing their own ``record_hash`` cannot even be loaded
  (``RunRecord.from_dict``), so a tampered record is refused by construction.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from logger.hashing import hash_object
from logger.run_records import RunRecord, read_jsonl
from runner.locks import load_locks, lock_hash

ARTIFACTS_DIR = Path("paper/artifacts")
BUILD_MANIFEST = Path("paper") / "build_manifest.json"
REFUSED_TAGS = ("smoke", "pilot-10pct")


class RefusedRun(RuntimeError):
    """Raised when a run may not enter a paper artifact."""


def eligible_runs(records: list[RunRecord], frozen_dir: str | Path) -> list[RunRecord]:
    """Filter records down to runs allowed in paper artifacts.

    Raises :class:`RefusedRun` naming the offending run — the generator stops,
    it does not silently skip.
    """
    locks = load_locks(frozen_dir)
    valid_lock_hashes = {lock_hash(lock) for lock in locks.values()}
    eligible: list[RunRecord] = []
    for rec in records:
        hit = [t for t in REFUSED_TAGS if t in rec.tags]
        if hit:
            raise RefusedRun(
                f"run {rec.run_id} carries non-paper tag(s) {hit} — "
                "smoke/pilot runs never enter paper tables (ADR-009)"
            )
        if rec.test_touched and (
            rec.test_lock_hash is None or rec.test_lock_hash not in valid_lock_hashes
        ):
            raise RefusedRun(
                f"run {rec.run_id} touched a test window but its test_lock_hash "
                "matches no freeze lock — refusing (pre-registration, AGENTS.md §2)"
            )
        eligible.append(rec)
    return eligible


def generate_table_artifact(
    table_id: str,
    records_path: str | Path,
    run_ids: list[str],
    frozen_dir: str | Path = "configs/frozen",
    artifacts_dir: str | Path = ARTIFACTS_DIR,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build ``paper/artifacts/<table_id>.json`` from the named runs.

    The artifact records every run_id, the run hashes, the generator git SHA,
    and the output sha256; the build manifest gains one entry. Returns the
    artifact document.
    """
    all_records = read_jsonl(records_path)
    by_id = {r.run_id: r for r in all_records}
    missing = [rid for rid in run_ids if rid not in by_id]
    if missing:
        raise RefusedRun(f"run_id(s) not found in {records_path}: {missing}")
    chosen = eligible_runs([by_id[rid] for rid in run_ids], frozen_dir)

    aggregate = {
        "n_runs": len(chosen),
        "metric_names": sorted({k for r in chosen for k in r.metrics}),
    }
    if extra:
        aggregate.update(extra)

    from logger.run_records import git_status

    artifact = {
        "table_id": table_id,
        "run_ids": [r.run_id for r in chosen],
        "run_hashes": [
            {
                "run_id": r.run_id,
                "config_hash": r.config_hash,
                "dataset_hash": r.dataset_hash,
                "dataset_split_hash": r.dataset_split_hash,
                "git_sha": r.git_sha,
                "record_hash": r.record_hash,
                "requirements_hash": r.requirements_hash,
                "tags": r.tags,
                "test_touched": r.test_touched,
                "test_lock_hash": r.test_lock_hash,
            }
            for r in chosen
        ],
        "aggregate": aggregate,
        "generator_git_sha": git_status()["git_sha"],
        "refusal_rules": {
            "tags": list(REFUSED_TAGS),
            "test_window_requires_lock": True,
        },
    }
    artifact["output_sha256"] = hash_object(
        {k: v for k, v in artifact.items() if k != "output_sha256"}
    )

    out_dir = Path(artifacts_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / f"{table_id}.json"
    out.write_text(json.dumps(artifact, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    manifest_path = Path(artifacts_dir).parent / "build_manifest.json"
    manifest: dict[str, Any] = {"artifacts": {}}
    if manifest_path.is_file():
        try:
            loaded = json.loads(manifest_path.read_text(encoding="utf-8"))
            if isinstance(loaded, dict) and isinstance(loaded.get("artifacts"), dict):
                manifest = loaded
        except json.JSONDecodeError:
            pass  # rebuild the manifest rather than propagate corruption
    manifest["artifacts"][table_id] = {
        "path": out.as_posix(),
        "output_sha256": artifact["output_sha256"],
        "run_ids": artifact["run_ids"],
    }
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return artifact
