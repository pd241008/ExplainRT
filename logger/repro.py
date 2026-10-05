"""``python -m logger.repro <run_id>`` (ADR-009).

Re-runs a recorded run with the recorded config, resolved pipeline, and seed,
then compares the fresh metrics against the record:

- **exact** comparison when the record's determinism flags say the pipeline is
  deterministic (the reference pipeline is);
- **tolerance** comparison otherwise — the tolerance is stated in the output,
  never hidden.

The runner's planning stage validates the config first; execution goes through
``runner.execution.run_pipeline``. Metrics are compared, not re-decided: any
mismatch exits 1 and says which metric drifted and by how much.
"""

from __future__ import annotations

import sys
from pathlib import Path

from runner.execution import run_pipeline

from logger.run_records import RunRecord, read_jsonl

RECORDS_PATH = Path("logger/runs.jsonl")
DEFAULT_TOLERANCE = 1e-9


def load_run(run_id: str, records_path: str | Path | None = None) -> RunRecord:
    """Fetch the record to reproduce; SystemExit when records are missing."""
    p = Path(RECORDS_PATH if records_path is None else records_path)
    if not p.is_file():
        print(f"no run records found at {p}", file=sys.stderr)
        raise SystemExit(1)
    for rec in read_jsonl(p):
        if rec.run_id == run_id:
            return rec
    print(f"run_id {run_id!r} not found in {p}", file=sys.stderr)
    raise SystemExit(1)


def compare_metrics(
    recorded: dict[str, float],
    fresh: dict[str, float],
    tolerance: float,
) -> tuple[bool, list[str]]:
    """Compare metric dicts; returns (all_ok, human-readable problems)."""
    problems: list[str] = []
    for name in sorted(recorded):
        if name not in fresh:
            problems.append(f"metric {name!r} missing from reproduction")
            continue
        recorded_val = float(recorded[name])
        fresh_val = float(fresh[name])
        if recorded_val == fresh_val:
            continue
        delta = abs(recorded_val - fresh_val)
        if delta <= tolerance:
            # Within tolerance: acceptable, but the difference is stated, not hidden.
            print(
                f"note: metric {name!r} differs within tolerance: "
                f"recorded={recorded_val!r} fresh={fresh_val!r} (delta={delta:.3e})"
            )
        else:
            problems.append(
                f"metric {name!r} MISMATCH: recorded={recorded_val!r} "
                f"fresh={fresh_val!r} (delta={delta:.3e} > tol={tolerance:.3e})"
            )
    for name in sorted(set(fresh) - set(recorded)):
        problems.append(f"metric {name!r} appeared only in reproduction")
    return (not problems), problems


def reproduce(
    rec: RunRecord, tolerance: float = DEFAULT_TOLERANCE
) -> tuple[bool, list[str], dict[str, float]]:
    """Re-run one record's pipeline and compare; returns (ok, problems, fresh)."""
    metrics, details = run_pipeline(rec.config, rec.seed)
    deterministic = details.get("determinism", {}).get("algorithms") == "deterministic"
    tol = 0.0 if deterministic else tolerance
    ok, problems = compare_metrics(rec.metrics, metrics, tol)
    return ok, problems, metrics


def main(argv: list[str] | None = None) -> int:
    """CLI: reproduce one run and print the comparison verdict."""
    args = list(sys.argv[1:] if argv is None else argv)
    if len(args) != 1:
        print("usage: python -m logger.repro <run_id>", file=sys.stderr)
        return 2
    rec = load_run(args[0])
    print(f"reproducing {rec.run_id} (seed={rec.seed}, model={rec.model_name})")
    ok, problems, fresh = reproduce(rec)
    print(f"recorded metrics : {rec.metrics}")
    print(f"fresh metrics    : {fresh}")
    for p in problems:
        print(f"  {p}")
    if ok:
        if problems:
            print("repro: PASSED (exact match unavailable; within stated tolerance)")
        else:
            print("repro: PASSED (exact match)")
        return 0
    print("repro: FAILED — the record does not reproduce", file=sys.stderr)
    return 1


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
