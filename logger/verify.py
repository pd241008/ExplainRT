"""``python -m logger.verify`` (ADR-009).

Recomputes every hash in the provenance chain:

- data: manifest entries vs. bytes in ``datasets/raw/`` (missing raw data is
  reported, not fabricated as verified)
- splits: side files vs. ``splits.lock.json``
- records: per-record hashes and the JSONL chain

Exit code 0 only when every check passes or is explicitly marked N/A. Any
mismatch prints ``FAIL`` lines and exits 1 — verification is loud or it is
nothing.
"""

from __future__ import annotations

import sys
from pathlib import Path

from logger.manifest import ManifestError, verify_data
from logger.run_records import verify_chain
from logger.splits import SplitError, verify_all_splits

RECORDS_PATH = Path("logger/runs.jsonl")


def verify_records(records_path: str | Path | None = None) -> list[str]:
    """Verify the record chain; return FAIL lines (empty = intact)."""
    p = Path(RECORDS_PATH if records_path is None else records_path)
    if not p.is_file():
        return [f"records: N/A — no record file at {p}"]
    problems = verify_chain(p)
    return [f"records: {p}" for p in problems] if problems else []


def run_all_checks(
    *,
    manifest_path: str | Path | None = None,
    raw_dir: str | Path | None = None,
    splits_dir: str | Path | None = None,
    records_path: str | Path | None = None,
) -> tuple[list[str], list[str]]:
    """Run data/split/record checks; return (ok_lines, fail_lines).

    All paths are optional and default to the repo-standard locations,
    resolved at call time.
    """
    ok: list[str] = []
    fail: list[str] = []

    # ── data manifest ──
    try:
        verified = verify_data(manifest_path=manifest_path, raw_dir=raw_dir)
        if verified:
            ok.append(f"data: {len(verified)} manifest entry(ies) verified")
        else:
            ok.append("data: N/A — manifest has no entries (no raw data ingested yet)")
    except ManifestError as exc:
        fail.append(f"data: {exc}")

    # ── splits ──
    try:
        names = verify_all_splits(splits_dir)
        if names:
            ok.append(f"splits: {len(names)} verified ({', '.join(names)})")
        else:
            ok.append("splits: N/A — splits.lock.json has no splits yet")
    except SplitError as exc:
        msg = str(exc)
        if "not found" in msg:
            ok.append("splits: N/A — no splits.lock.json yet")
        else:
            fail.append(f"splits: {msg}")

    # ── record chain ──
    rec_fail = verify_records(records_path)
    if rec_fail and rec_fail[0].startswith("records: N/A"):
        ok.append(rec_fail[0])
    elif rec_fail:
        fail.extend(rec_fail)
    else:
        ok.append("records: hash chain intact")
    return ok, fail


def main(argv: list[str] | None = None) -> int:
    """CLI entry: print per-domain verdicts; exit 1 on any failure."""
    del argv
    ok, fail = run_all_checks()
    for line in ok:
        print(f"  OK  {line}" if "N/A" not in line else f"  --  {line}")
    for line in fail:
        print(f"FAIL  {line}", file=sys.stderr)
    if fail:
        print(f"verify: {len(fail)} check(s) failed", file=sys.stderr)
        return 1
    print("verify: all provenance checks passed")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
