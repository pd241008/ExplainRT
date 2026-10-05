"""Unit tests for logger.splits (ADR-009).

Acceptance test 3 (prompt): the split hash changes if one ID is added,
removed, or reordered into a different split. Synthetic sha256 IDs only —
no real samples (AGENTS.md §7).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from logger.hashing import hash_split_ids
from logger.splits import (
    SIDES,
    SplitError,
    load_splits_lock,
    make_lock_entry,
    read_split_ids,
    side_hashes,
    split_hash,
    verify_all_splits,
    verify_split,
    write_split_ids,
    write_splits_lock,
)

IDS_A = [f"{i:064x}" for i in range(10)]
IDS_B = [f"{i:064x}" for i in range(10, 20)]
IDS_C = [f"{i:064x}" for i in range(20, 25)]


def _ids_by_side() -> dict[str, list[str]]:
    return {"train": IDS_A, "val": IDS_B, "test": IDS_C}


def _lock_entry() -> dict:
    return make_lock_entry(
        name="time_aware_v1",
        ids_by_side=_ids_by_side(),
        algorithm="time_aware",
        algorithm_version="1",
        seed=42,
        dataset_hash="d" * 64,
        window_boundaries={"train_end": "2020-05-01", "val_end": "2020-08-01"},
    )


class TestSplitFiles:
    def test_round_trip_sorted(self, tmp_path: Path) -> None:
        p = write_split_ids(tmp_path / "s" / "train.txt", list(reversed(IDS_A)))
        assert read_split_ids(p) == IDS_A  # stored sorted

    def test_rejects_non_sha256_ids(self, tmp_path: Path) -> None:
        p = tmp_path / "train.txt"
        p.write_text("sample_0001\n", encoding="utf-8")
        with pytest.raises(SplitError, match="sha256"):
            read_split_ids(p)

    def test_rejects_duplicates_and_unsorted(self, tmp_path: Path) -> None:
        p = tmp_path / "train.txt"
        p.write_text("\n".join([IDS_A[0], IDS_A[0]]) + "\n", encoding="utf-8")
        with pytest.raises(SplitError, match="duplicate"):
            read_split_ids(p)
        p.write_text("\n".join([IDS_A[1], IDS_A[0]]) + "\n", encoding="utf-8")
        with pytest.raises(SplitError, match="sorted"):
            read_split_ids(p)

    def test_missing_file_raises(self, tmp_path: Path) -> None:
        with pytest.raises(SplitError, match="not found"):
            read_split_ids(tmp_path / "nope.txt")

    def test_write_rejects_bad_ids(self, tmp_path: Path) -> None:
        with pytest.raises(SplitError, match="refusing"):
            write_split_ids(tmp_path / "x.txt", ["../etc/passwd"])


class TestSplitHash:
    """Acceptance test 3: one-ID changes always change the split hash."""

    def test_stable_for_identical_splits(self) -> None:
        assert split_hash(_ids_by_side()) == split_hash(_ids_by_side())

    def test_added_id_changes_hash(self) -> None:
        base = split_hash(_ids_by_side())
        changed = _ids_by_side()
        changed["train"] = sorted(changed["train"] + [f"{99:064x}"])
        assert split_hash(changed) != base

    def test_removed_id_changes_hash(self) -> None:
        base = split_hash(_ids_by_side())
        changed = _ids_by_side()
        changed["val"] = changed["val"][1:]
        assert split_hash(changed) != base

    def test_id_moved_between_sides_changes_hash(self) -> None:
        base = split_hash(_ids_by_side())
        changed = _ids_by_side()
        moved = changed["val"][0]
        changed["val"] = changed["val"][1:]
        changed["test"] = sorted(changed["test"] + [moved])
        assert split_hash(changed) != base

    def test_side_hashes_are_independent(self) -> None:
        h = side_hashes(_ids_by_side())
        assert set(h) == set(SIDES)
        assert len(set(h.values())) == 3

    def test_input_order_is_canonicalized(self) -> None:
        # side_hashes/split_hash canonicalize (sort) their input; the strict
        # "must be pre-sorted" contract lives in hash_split_ids/read_split_ids.
        shuffled = {"train": list(reversed(IDS_A)), "val": IDS_B, "test": IDS_C}
        assert split_hash(shuffled) == split_hash(_ids_by_side())
        with pytest.raises(ValueError, match="sorted"):
            hash_split_ids(list(reversed(IDS_A)))


class TestSplitsLock:
    def test_entry_contains_spec(self) -> None:
        entry = _lock_entry()
        assert entry["counts"] == {"train": 10, "val": 10, "test": 5}
        assert entry["split_hash"] == split_hash(_ids_by_side())
        assert entry["window_boundaries"]["train_end"] == "2020-05-01"
        assert "sampling_fraction" not in entry  # not applicable here

    def test_unknown_algorithm_rejected(self) -> None:
        with pytest.raises(SplitError, match="unknown split algorithm"):
            make_lock_entry(
                name="x",
                ids_by_side=_ids_by_side(),
                algorithm="vibes",
                algorithm_version="1",
                seed=0,
                dataset_hash="d" * 64,
            )

    def test_lock_round_trip_and_verify(self, tmp_path: Path) -> None:
        entry = _lock_entry()
        write_splits_lock({"time_aware_v1": entry}, tmp_path)
        doc = json.loads((tmp_path / "splits.lock.json").read_text(encoding="utf-8"))
        assert "time_aware_v1" in doc["splits"]
        for side in SIDES:
            write_split_ids(tmp_path / "time_aware_v1" / f"{side}.txt", _ids_by_side()[side])
        assert verify_split("time_aware_v1", tmp_path) == entry
        assert verify_all_splits(tmp_path) == ["time_aware_v1"]

    def test_verify_detects_file_tampering(self, tmp_path: Path) -> None:
        write_splits_lock({"time_aware_v1": _lock_entry()}, tmp_path)
        for side in SIDES:
            write_split_ids(tmp_path / "time_aware_v1" / f"{side}.txt", _ids_by_side()[side])
        # Swap one ID from train into test inside the *file only*.
        train = tmp_path / "time_aware_v1" / "train.txt"
        test = tmp_path / "time_aware_v1" / "test.txt"
        stolen = train.read_text(encoding="utf-8").splitlines()[0]
        kept = train.read_text(encoding="utf-8").splitlines()[1:]
        # Same count on both sides (swapped), so the count check passes and the
        # hash check is what must catch the tampering.
        train.write_text("\n".join(kept + [IDS_C[0]]) + "\n", encoding="utf-8")
        test.write_text(
            "\n".join(sorted(test.read_text(encoding="utf-8").splitlines() + [stolen])) + "\n",
            encoding="utf-8",
        )
        assert train.read_text(encoding="utf-8").splitlines() != sorted(kept + [stolen])
        with pytest.raises(SplitError, match="hash mismatch"):
            verify_split("time_aware_v1", tmp_path)

    def test_verify_detects_count_change(self, tmp_path: Path) -> None:
        write_splits_lock({"time_aware_v1": _lock_entry()}, tmp_path)
        for side in SIDES:
            write_split_ids(tmp_path / "time_aware_v1" / f"{side}.txt", _ids_by_side()[side])
        p = tmp_path / "time_aware_v1" / "train.txt"
        p.write_text(
            "\n".join(p.read_text(encoding="utf-8").splitlines()[:-1]) + "\n", encoding="utf-8"
        )
        with pytest.raises(SplitError, match="count mismatch"):
            verify_split("time_aware_v1", tmp_path)

    def test_missing_lock_raises(self, tmp_path: Path) -> None:
        with pytest.raises(SplitError, match="not found"):
            load_splits_lock(tmp_path)

    def test_subset_lock_records_stratification(self) -> None:
        entry = make_lock_entry(
            name="pilot_10pct",
            ids_by_side=_ids_by_side(),
            algorithm="random",
            algorithm_version="1",
            seed=7,
            dataset_hash="d" * 64,
            sampling_fraction=0.1,
            stratification={"by": ["month", "family"], "frozen_id_list": True},
        )
        assert entry["sampling_fraction"] == 0.1
        assert entry["stratification"]["by"] == ["month", "family"]
        # Defined only by frozen ID list + seed: the hash pins both.
        assert entry["split_hash"] == split_hash(_ids_by_side())
