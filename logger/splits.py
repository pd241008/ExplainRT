"""Sample IDs and splits (ADR-009).

The canonical sample ID is the sample's SHA-256 (the BODMAS sha). Sample paths
and contents are never logged — hashes and counts only (hard rule, AGENTS.md
§2; ADR-006).

Layout:

- ``datasets/splits/<name>/<split>.txt`` — one sorted sample ID per line
  (``split`` ∈ train/val/test)
- ``datasets/splits/splits.lock.json`` — per split ``<name>``: sample counts,
  ``split_hash`` (hash of the sorted ID list of every side), and the split
  spec (algorithm version, seed, window boundaries, sampling fraction,
  ``dataset_hash``)

The 10% subsets are stratified by month and family and are defined only by a
frozen ID list plus seed — no resampling at run time.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from logger.hashing import hash_object, hash_split_ids

SPLITS_DIR = Path("datasets/splits")
SPLITS_LOCK_NAME = "splits.lock.json"
SIDES = ("train", "val", "test")
KNOWN_ALGORITHMS = ("random", "near_duplicate", "time_aware", "open_set")


class SplitError(RuntimeError):
    """Raised for malformed split files or lock inconsistencies."""


def read_split_ids(path: str | Path) -> list[str]:
    """Read a split side file: sorted, deduplicated 64-hex sample IDs."""
    p = Path(path)
    if not p.is_file():
        raise SplitError(f"split file not found: {p}")
    ids = [line.strip() for line in p.read_text(encoding="utf-8").splitlines() if line.strip()]
    bad = [i for i in ids if len(i) != 64 or any(c not in "0123456789abcdef" for c in i)]
    if bad:
        raise SplitError(
            f"{p}: sample IDs must be 64-char lowercase sha256 hex; got e.g. {bad[:3]}"
        )
    if len(set(ids)) != len(ids):
        raise SplitError(f"{p}: duplicate sample IDs")
    if ids != sorted(ids):
        raise SplitError(f"{p}: IDs must be stored sorted (canonical form)")
    return ids


def write_split_ids(path: str | Path, ids: list[str]) -> Path:
    """Write one side's sample IDs, sorted, one per line."""
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    for i in ids:
        if len(i) != 64 or any(c not in "0123456789abcdef" for c in i):
            raise SplitError(f"refusing to write non-sha256 sample ID: {i!r}")
    p.write_text("\n".join(sorted(ids)) + ("\n" if ids else ""), encoding="utf-8")
    return p


def side_hashes(ids_by_side: dict[str, list[str]]) -> dict[str, str]:
    """Per-side split hashes (hash of each sorted ID list)."""
    wrong = set(ids_by_side) - set(SIDES)
    if wrong:
        raise SplitError(f"unknown split sides: {sorted(wrong)}")
    return {side: hash_split_ids(sorted(ids_by_side[side])) for side in SIDES}


def split_hash(ids_by_side: dict[str, list[str]]) -> str:
    """Hash of a whole split: the canonical object of all side hashes.

    Adding, removing, or moving one ID between sides changes this hash
    (acceptance test 3).
    """
    return hash_object(side_hashes(ids_by_side))


def make_lock_entry(
    *,
    name: str,
    ids_by_side: dict[str, list[str]],
    algorithm: str,
    algorithm_version: str,
    seed: int,
    dataset_hash: str,
    window_boundaries: dict[str, str] | None = None,
    sampling_fraction: float | None = None,
    stratification: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build one ``splits.lock.json`` entry for split ``name``.

    ``window_boundaries`` (time-aware), ``sampling_fraction`` (subsets), and
    ``stratification`` (month/family strata for the 10% subsets) are recorded
    when applicable; ``None`` fields are omitted so the lock shows exactly the
    spec that applies.
    """
    if algorithm not in KNOWN_ALGORITHMS:
        raise SplitError(
            f"unknown split algorithm {algorithm!r}; expected one of {KNOWN_ALGORITHMS}"
        )
    entry: dict[str, Any] = {
        "algorithm": algorithm,
        "algorithm_version": algorithm_version,
        "seed": int(seed),
        "dataset_hash": dataset_hash,
        "counts": {side: len(ids_by_side[side]) for side in SIDES},
        "side_hashes": side_hashes(ids_by_side),
        "split_hash": split_hash(ids_by_side),
    }
    if window_boundaries is not None:
        entry["window_boundaries"] = window_boundaries
    if sampling_fraction is not None:
        entry["sampling_fraction"] = sampling_fraction
    if stratification is not None:
        entry["stratification"] = stratification
    return entry


def write_splits_lock(
    entries: dict[str, dict[str, Any]],
    splits_dir: str | Path = SPLITS_DIR,
) -> Path:
    """Write ``splits.lock.json`` from ``{name: entry}`` (sorted keys)."""
    p = Path(splits_dir) / SPLITS_LOCK_NAME
    p.parent.mkdir(parents=True, exist_ok=True)
    doc = {"schema_version": 1, "splits": dict(sorted(entries.items()))}
    p.write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return p


def load_splits_lock(splits_dir: str | Path = SPLITS_DIR) -> dict[str, Any]:
    """Load ``splits.lock.json``; raises :class:`SplitError` when absent/bad."""
    p = Path(splits_dir) / SPLITS_LOCK_NAME
    if not p.is_file():
        raise SplitError(f"splits lock not found: {p}")
    try:
        doc = json.loads(p.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise SplitError(f"{p} is not valid JSON: {exc}") from exc
    if not isinstance(doc, dict) or not isinstance(doc.get("splits"), dict):
        raise SplitError(f"{p} must contain a 'splits' mapping")
    return doc["splits"]


def verify_split(
    name: str,
    splits_dir: str | Path = SPLITS_DIR,
) -> dict[str, Any]:
    """Recompute a named split's side files against its lock entry.

    Returns the lock entry on success; raises :class:`SplitError` on any
    mismatch (counts, per-side hashes, or whole-split hash).
    """
    lock = load_splits_lock(splits_dir)
    if name not in lock:
        raise SplitError(f"split {name!r} not in splits.lock.json")
    entry = lock[name]
    ids_by_side: dict[str, list[str]] = {}
    for side in SIDES:
        side_path = Path(splits_dir) / name / f"{side}.txt"
        ids_by_side[side] = read_split_ids(side_path)
        if len(ids_by_side[side]) != entry["counts"][side]:
            raise SplitError(
                f"split {name!r} side {side!r}: count mismatch "
                f"(lock {entry['counts'][side]}, file {len(ids_by_side[side])})"
            )
        actual = hash_split_ids(sorted(ids_by_side[side]))
        if actual != entry["side_hashes"][side]:
            raise SplitError(f"split {name!r} side {side!r}: hash mismatch")
    actual_split = split_hash(ids_by_side)
    if actual_split != entry["split_hash"]:
        raise SplitError(f"split {name!r}: split_hash mismatch")
    return entry


def verify_all_splits(splits_dir: str | Path = SPLITS_DIR) -> list[str]:
    """Verify every split recorded in the lock; return verified names."""
    lock = load_splits_lock(splits_dir)
    for name in lock:
        verify_split(name, splits_dir)
    return sorted(lock)
