"""Freeze / lock mechanism for pre-registration (ADR-009).

Pre-registration (hard rule, AGENTS.md §2: never tune on test windows) becomes
mechanical here:

- ``freeze`` writes ``configs/frozen/<name>.lock`` containing config_hash,
  split_hash, dataset_hash, git_sha, and the date — *before* the runs that
  will be checked against it.
- Evaluating a locked test window is allowed only for runs whose hashes match
  a lock; :func:`check_lock` raises otherwise, and the runner refuses
  (acceptance test 7).
- Headline (``final``-tagged) runs additionally require a clean git tree and a
  matching lock (acceptance test 6).

Locks are tracked in git: a lock is a commitment, and commitments are
reviewable. The freeze date and git SHA make "chosen after seeing test
results" detectable in history.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from logger.hashing import hash_object

FROZEN_DIR = Path("configs/frozen")


class LockError(RuntimeError):
    """Raised when a run cannot proceed under the pre-registration rules."""


def freeze(
    name: str,
    *,
    config_hash: str,
    split_hash: str,
    dataset_hash: str,
    git_sha: str | None,
    frozen_dir: str | Path = FROZEN_DIR,
    date: str | None = None,
    note: str | None = None,
) -> Path:
    """Write ``configs/frozen/<name>.lock`` and return its path.

    Called *before* any run that will be gated by the lock. Existing locks are
    never silently overwritten — freezing is a commitment; supersede explicitly
    with a new name (and an ADR note).
    """
    p = Path(frozen_dir) / f"{name}.lock"
    if p.exists():
        raise LockError(f"lock already exists: {p} — freeze is immutable; use a new name")
    lock = {
        "name": name,
        "config_hash": config_hash,
        "split_hash": split_hash,
        "dataset_hash": dataset_hash,
        "git_sha": git_sha,
        "date": date,
        "note": note,
    }
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(lock, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return p


def load_locks(frozen_dir: str | Path = FROZEN_DIR) -> dict[str, dict[str, Any]]:
    """Load every ``*.lock`` file, keyed by lock name. Missing dir → empty."""
    locks: dict[str, dict[str, Any]] = {}
    d = Path(frozen_dir)
    if not d.is_dir():
        return locks
    for p in sorted(d.glob("*.lock")):
        try:
            lock = json.loads(p.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise LockError(f"{p} is not valid JSON: {exc}") from exc
        if not isinstance(lock, dict) or "config_hash" not in lock:
            raise LockError(f"{p} is malformed for a lock file")
        locks[lock.get("name", p.stem)] = lock
    return locks


def match_lock(
    *,
    config_hash: str,
    split_hash: str | None,
    dataset_hash: str | None,
    frozen_dir: str | Path = FROZEN_DIR,
) -> dict[str, Any] | None:
    """Return the lock whose hashes match the run's, or None.

    All three hashes must match when the lock records them.
    """
    for lock in load_locks(frozen_dir).values():
        if lock.get("config_hash") != config_hash:
            continue
        if lock.get("split_hash") not in (None, split_hash):
            continue
        if lock.get("dataset_hash") not in (None, dataset_hash):
            continue
        return lock
    return None


def check_lock(
    *,
    config_hash: str,
    split_hash: str | None = None,
    dataset_hash: str | None = None,
    test_touched: bool,
    frozen_dir: str | Path = FROZEN_DIR,
) -> dict[str, Any] | None:
    """Gate for evaluating a test window (acceptance test 7).

    - ``test_touched=False`` → no lock needed; returns None.
    - ``test_touched=True`` → a matching lock must exist, else
      :class:`LockError` (the runner refuses).
    """
    if not test_touched:
        return None
    lock = match_lock(
        config_hash=config_hash,
        split_hash=split_hash,
        dataset_hash=dataset_hash,
        frozen_dir=frozen_dir,
    )
    if lock is None:
        raise LockError(
            "run touches a locked test window but no freeze lock matches its "
            f"(config_hash={config_hash[:12]}, split_hash={split_hash}, "
            f"dataset_hash={dataset_hash}) — freeze first: "
            "python -m runner.locks freeze <name> ..."
        )
    return lock


def check_final_run(
    *,
    config_hash: str,
    split_hash: str | None = None,
    dataset_hash: str | None = None,
    git_dirty: bool | None,
    tags: list[str],
    frozen_dir: str | Path = FROZEN_DIR,
) -> dict[str, Any] | None:
    """Gate for headline (``final``) runs (acceptance test 6).

    A final run must come from a clean git tree AND a matching freeze lock.
    ``git_dirty=None`` (git unavailable) blocks final runs too: an unverifiable
    tree is not a clean tree.
    """
    if "final" not in tags:
        return None
    if git_dirty is None or git_dirty:
        state = "unavailable" if git_dirty is None else "dirty"
        raise LockError(
            f"refusing a 'final' run from a {state} git tree — commit first "
            "(ADR-009: headline runs must be reproducible from committed code)"
        )
    return check_lock(
        config_hash=config_hash,
        split_hash=split_hash,
        dataset_hash=dataset_hash,
        test_touched=True,
        frozen_dir=frozen_dir,
    )


def lock_hash(lock: dict[str, Any]) -> str:
    """Canonical hash of a lock's contents (recorded in run records as
    ``test_lock_hash`` — the exact commitment a run was evaluated under)."""
    return hash_object(lock)


def main(argv: list[str] | None = None) -> int:
    """CLI for freezing and listing locks.

    Usage::

        python -m runner.locks freeze <name> --config-hash H --split-hash H \\
            --dataset-hash H --git-sha SHA [--note "..."]
        python -m runner.locks list
    """
    import argparse
    import sys
    from datetime import UTC, datetime

    parser = argparse.ArgumentParser(prog="runner.locks")
    sub = parser.add_subparsers(dest="cmd", required=True)
    p_freeze = sub.add_parser("freeze", help="write a pre-registration lock")
    p_freeze.add_argument("name")
    p_freeze.add_argument("--config-hash", required=True)
    p_freeze.add_argument("--split-hash", default=None)
    p_freeze.add_argument("--dataset-hash", default=None)
    p_freeze.add_argument("--git-sha", default=None)
    p_freeze.add_argument("--note", default=None)
    sub.add_parser("list", help="list existing locks")
    args = parser.parse_args(list(sys.argv[1:] if argv is None else argv))

    if args.cmd == "list":
        locks = load_locks()
        if not locks:
            print("no locks in configs/frozen/")
            return 0
        for name, lock in locks.items():
            print(f"{name}: config={lock['config_hash'][:12]} date={lock.get('date')}")
        return 0

    try:
        p = freeze(
            args.name,
            config_hash=args.config_hash,
            split_hash=args.split_hash,
            dataset_hash=args.dataset_hash,
            git_sha=args.git_sha,
            date=datetime.now(UTC).strftime("%Y-%m-%d"),
            note=args.note,
        )
    except LockError as exc:
        print(f"freeze refused: {exc}", file=sys.stderr)
        return 1
    print(f"froze {args.name} -> {p}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
