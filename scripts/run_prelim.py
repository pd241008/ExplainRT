#!/usr/bin/env python3
"""Preliminary R1 run executor (ADR-008 rev 2; ADR-009 provenance).

Steps, in order, refusing loudly at any failure:

1. ``logger.manifest.verify_data(['bodmas_features'])`` — the only raw source
   this regime consumes is verified against the tracked manifest.
2. Plan runs from ``configs/p1_prelim_r1_bodmas.yaml`` via the runner's
   ``plan_from_config`` (config is validated there).
3. For each planned run, execute the deterministic reference pipeline
   (``runner.execution.run_pipeline``), then append through
   ``RunRecorder.start/finish`` + ``append_jsonl`` so the record carries the
   derived run ID, full provenance, tags ``[smoke, prelim, R1]``, and enters
   the tamper-evident chain in ``logger/runs.jsonl``.

No number from this run can reach tables: the ``smoke`` tag makes
``paper/tables.py`` refuse it (ADR-009).
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from logger.manifest import dataset_hash, verify_data
from logger.run_records import RunRecorder, append_jsonl
from runner.execution import DETERMINISM_FLAGS, run_pipeline
from runner.experiment import load_config, plan_from_config

CONFIG_PATH = Path("configs/p1_prelim_r1_bodmas.yaml")
RECORDS_PATH = Path("logger/runs.jsonl")
TAGS = ["smoke", "prelim", "R1"]


def done_identities(path: Path) -> set[tuple[str, str, int, str]]:
    """Resume: identities of runs already recorded in the file."""
    from logger.run_records import read_jsonl

    if not path.is_file():
        return set()
    return {
        (r.config.get("experiment", ""), r.model_name, r.seed, r.config_hash)
        for r in read_jsonl(path)
    }


def main() -> int:
    # 1. Verify the exact source this regime consumes, before any run.
    verified = verify_data(["bodmas_features"])
    print(f"verify-data OK: {verified}")
    ds_hash = dataset_hash(["bodmas_features"])
    print(f"dataset_hash = {ds_hash[:12]}")

    # 2. Plan (this also validates the config and seed contract).
    cfg = load_config(CONFIG_PATH)
    plan = plan_from_config(cfg)
    done = done_identities(RECORDS_PATH)
    print(f"planned_runs={len(plan)} already_recorded={len(done)}")

    skipped, executed = 0, 0
    recorder = RunRecorder(output_dir=str(RECORDS_PATH.parent))
    for p in plan:
        if p.identity in done:
            skipped += 1
            print(f"skip seed={p.seed} (resume)")
            continue
        t0 = time.perf_counter()
        # 3. Execute the deterministic reference pipeline.
        metrics, details = run_pipeline(p.config, p.seed)
        wall = time.perf_counter() - t0
        rec = recorder.start(
            config=p.config,
            seed=p.seed,
            model_name=p.model_name,
            dataset_hash=ds_hash,
            split_name=str(cfg.get("split_protocol")),
            tags=list(TAGS),
            determinism=dict(DETERMINISM_FLAGS),
        )
        rec = RunRecorder.finish(rec, metrics=metrics, wall_time_sec=wall)
        rec = append_jsonl(rec, RECORDS_PATH)
        executed += 1
        print(f"recorded run_id={rec.run_id} seed={p.seed} metrics={metrics}")
    print(f"executed={executed} skipped={skipped} total_records_append_only")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
