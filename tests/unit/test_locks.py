"""Unit tests for runner.locks (ADR-009).

Acceptance test 6 (prompt): a dirty git tree blocks a ``final`` run.
Acceptance test 7 (prompt): the runner refuses to evaluate locked test
windows without a matching lock.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from runner.locks import (
    LockError,
    check_final_run,
    check_lock,
    freeze,
    load_locks,
    lock_hash,
)

CFG_H = "c" * 64
SPLIT_H = "s" * 64
DATA_H = "d" * 64


@pytest.fixture()
def frozen(tmp_path: Path) -> Path:
    freeze(
        "pilot_v1",
        config_hash=CFG_H,
        split_hash=SPLIT_H,
        dataset_hash=DATA_H,
        git_sha="abc123",
        frozen_dir=tmp_path,
        date="2026-10-05",
    )
    return tmp_path


class TestFreeze:
    def test_lock_written_and_loadable(self, frozen: Path) -> None:
        locks = load_locks(frozen)
        assert "pilot_v1" in locks
        lock = locks["pilot_v1"]
        assert lock["config_hash"] == CFG_H
        assert lock["split_hash"] == SPLIT_H
        assert lock["dataset_hash"] == DATA_H
        assert lock["git_sha"] == "abc123"
        assert lock["date"] == "2026-10-05"

    def test_no_silent_overwrite(self, frozen: Path) -> None:
        with pytest.raises(LockError, match="immutable"):
            freeze(
                "pilot_v1",
                config_hash="0" * 64,
                split_hash="1" * 64,
                dataset_hash="2" * 64,
                git_sha=None,
                frozen_dir=frozen,
            )

    def test_malformed_lock_rejected(self, tmp_path: Path) -> None:
        (tmp_path / "bad.lock").write_text("{}", encoding="utf-8")
        with pytest.raises(LockError, match="malformed"):
            load_locks(tmp_path)


class TestLockGating:
    """Acceptance test 7: no test window without a matching lock."""

    def test_no_lock_needed_without_test(self) -> None:
        assert check_lock(config_hash=CFG_H, test_touched=False) is None

    def test_refuses_without_matching_lock(self) -> None:
        with pytest.raises(LockError, match="freeze first"):
            check_lock(
                config_hash=CFG_H,
                split_hash=SPLIT_H,
                dataset_hash=DATA_H,
                test_touched=True,
            )

    def test_allows_with_matching_lock(self, frozen: Path) -> None:
        lock = check_lock(
            config_hash=CFG_H,
            split_hash=SPLIT_H,
            dataset_hash=DATA_H,
            test_touched=True,
            frozen_dir=frozen,
        )
        assert lock is not None and lock["name"] == "pilot_v1"

    def test_hash_mismatch_refuses_even_with_lock(self, frozen: Path) -> None:
        with pytest.raises(LockError, match="no freeze lock matches"):
            check_lock(
                config_hash=CFG_H,
                split_hash="9" * 64,  # different split than frozen
                dataset_hash=DATA_H,
                test_touched=True,
                frozen_dir=frozen,
            )
        with pytest.raises(LockError, match="no freeze lock matches"):
            check_lock(
                config_hash="9" * 64,  # different config than frozen
                split_hash=SPLIT_H,
                dataset_hash=DATA_H,
                test_touched=True,
                frozen_dir=frozen,
            )


class TestFinalRunGate:
    """Acceptance test 6: dirty tree blocks a final run."""

    def test_dirty_tree_blocks_final(self, frozen: Path) -> None:
        with pytest.raises(LockError, match="dirty git tree"):
            check_final_run(
                config_hash=CFG_H,
                split_hash=SPLIT_H,
                dataset_hash=DATA_H,
                git_dirty=True,
                tags=["final"],
                frozen_dir=frozen,
            )

    def test_unknown_git_state_blocks_final(self, frozen: Path) -> None:
        with pytest.raises(LockError, match="unavailable"):
            check_final_run(
                config_hash=CFG_H,
                split_hash=SPLIT_H,
                dataset_hash=DATA_H,
                git_dirty=None,
                tags=["final"],
                frozen_dir=frozen,
            )

    def test_clean_tree_with_lock_passes(self, frozen: Path) -> None:
        lock = check_final_run(
            config_hash=CFG_H,
            split_hash=SPLIT_H,
            dataset_hash=DATA_H,
            git_dirty=False,
            tags=["final"],
            frozen_dir=frozen,
        )
        assert lock is not None

    def test_clean_tree_without_lock_fails(self, tmp_path: Path) -> None:
        with pytest.raises(LockError, match="freeze first"):
            check_final_run(
                config_hash=CFG_H,
                split_hash=SPLIT_H,
                dataset_hash=DATA_H,
                git_dirty=False,
                tags=["final"],
                frozen_dir=tmp_path,
            )

    def test_non_final_runs_unaffected(self, tmp_path: Path) -> None:
        assert (
            check_final_run(
                config_hash=CFG_H,
                split_hash=SPLIT_H,
                dataset_hash=DATA_H,
                git_dirty=True,
                tags=["smoke", "pilot-10pct"],
                frozen_dir=tmp_path,
            )
            is None
        )


class TestLockHash:
    def test_lock_hash_is_stable_and_binding(self, frozen: Path) -> None:
        lock = load_locks(frozen)["pilot_v1"]
        assert lock_hash(lock) == lock_hash(dict(lock))
        changed = {**lock, "note": "amended after the fact"}
        assert lock_hash(changed) != lock_hash(lock)
