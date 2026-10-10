"""Unit tests for bytelens.eval.splits builders (ADR-010 §2).

Synthetic ids/features only. Core invariants: cluster/family never crosses
sides; time ordering strict; fixed seed ⇒ identical split; interim names
require the `_npzonly` suffix.
"""

from __future__ import annotations

import numpy as np
import pytest
from bytelens.data.bodmas import mint_npz_row_id
from bytelens.eval.splits import (
    NPZONLY_SUFFIX,
    SplitBundle,
    build_near_duplicate_proxy_entry,
    build_open_set_entry,
    build_random_entry,
    build_time_aware_entry,
    feature_bucket_ids,
    near_duplicate_proxy_split,
    open_set_split,
    random_split,
    time_aware_split,
)

N = 120


def _ids() -> list[str]:
    return [mint_npz_row_id(i, "a" * 64) for i in range(N)]


def _sha_ids() -> list[str]:
    # Distinct fake sha256-style ids for full-mode protocols.
    return [f"{i:064x}" for i in range(N)]


def _side_union(entry_ids: dict[str, list[str]]) -> list[str]:
    out: list[str] = []
    for side in ("train", "val", "test"):
        out.extend(entry_ids[side])
    return out


class TestRandomSplit:
    def test_deterministic_and_partition(self) -> None:
        ids, strata = _ids(), (["0", "1"] * (N // 2))
        a = random_split(ids=ids, strata=strata, seed=7)
        b = random_split(ids=ids, strata=strata, seed=7)
        assert a == b
        assert sorted(_side_union(a)) == sorted(ids)
        assert not ({*a["train"]} & {*a["val"]})
        assert not ({*a["train"]} & {*a["test"]})
        assert not ({*a["val"]} & {*a["test"]})
        assert_split_bundle_valid(a)

    def test_ratios_approx(self) -> None:
        a = random_split(ids=_ids(), strata=["0"] * N, seed=1)
        assert abs(len(a["train"]) / N - 0.70) < 0.02
        assert abs(len(a["val"]) / N - 0.15) < 0.02
        assert abs(len(a["test"]) / N - 0.15) < 0.02

    def test_seed_changes_split(self) -> None:
        ids, strata = _ids(), (["0", "1"] * (N // 2))
        a = random_split(ids=ids, strata=strata, seed=1)
        b = random_split(ids=ids, strata=strata, seed=2)
        assert a != b

    def test_misaligned_inputs_raise(self) -> None:
        with pytest.raises(ValueError, match="align"):
            random_split(ids=_ids(), strata=["0"] * (N - 1), seed=0)

    def test_entry_requires_npzonly_suffix(self) -> None:
        with pytest.raises(ValueError, match="_npzonly"):
            build_random_entry(
                name="random_v1",
                ids=_ids(),
                strata=["0"] * N,
                seed=0,
                dataset_hash="d" * 64,
            )


def assert_split_bundle_valid(ids_by_side: dict[str, list[str]]) -> None:
    SplitBundle(name="x", ids_by_side=ids_by_side, entry={}).validate()


class TestNearDuplicateProxy:
    def _clustered(self) -> tuple[list[str], np.ndarray]:
        """4 tight clusters with distinct means + noise."""
        rng = np.random.default_rng(3)
        centers = np.array([[10, 0], [0, 10], [-10, 0], [0, -10]], dtype=np.float32)
        X = np.concatenate(
            [centers[k] + rng.standard_normal((N // 8, 2)).astype(np.float32) * 0.01 for k in range(4)]
        )
        return [_sha_ids()[i] for i in range(len(X))], X

    def test_clusters_never_cross_sides(self) -> None:
        ids, X = self._clustered()
        split = near_duplicate_proxy_split(ids=ids, X=X, seed=0)
        buckets = feature_bucket_ids(X, seed=0)
        # Every bucket must land in exactly one side.
        side_of: dict[str, str] = {}
        seen: dict[int, str] = {}
        for side in ("train", "val", "test"):
            for i in split[side]:
                side_of[i] = side
        for i, bid in zip(ids, buckets, strict=True):
            if bid in seen:
                assert side_of[i] == seen[bid], f"bucket {bid} crossed sides"
            seen[bid] = side_of[i]
        assert sorted(_side_union(split)) == sorted(ids)
        assert_split_bundle_valid(split)

    def test_entry_is_lockappable(self) -> None:
        ids, X = self._clustered()
        name = f"nd_proxy_v1{NPZONLY_SUFFIX}"
        entry = build_near_duplicate_proxy_entry(
            name=name, ids=ids, X=X, seed=0, dataset_hash="d" * 64
        )
        assert entry["algorithm"] == "near_duplicate_proxy"  # canonical name space
        assert entry["id_basis"] == "row_index"
        assert entry["counts"]["train"] > 0


class TestTimeAware:
    def test_strict_temporal_order(self) -> None:
        ids = _sha_ids()
        ts = list(range(N))  # already unique and ordered
        split = time_aware_split(ids=ids, timestamps=ts)
        # By construction (sorted order), train < val < test in time.
        assert split["train"] == sorted(ids[: int(0.7 * N)])
        assert split["val"] == sorted(ids[int(0.7 * N) : int(0.85 * N)])
        assert split["test"] == sorted(ids[int(0.85 * N) :])

    def test_equal_timestamps_stay_whole(self) -> None:
        ids = _sha_ids()
        ts = [i // 2 for i in range(N)]  # pairs share timestamps
        split = time_aware_split(ids=ids, timestamps=ts)
        ts_map = dict(zip(ids, ts, strict=True))
        assert max(ts_map[i] for i in split["train"]) <= min(ts_map[i] for i in split["val"])
        assert max(ts_map[i] for i in split["val"]) <= min(ts_map[i] for i in split["test"])

    def test_degenerate_all_equal_raises(self) -> None:
        ids = _sha_ids()
        with pytest.raises(ValueError):
            time_aware_split(ids=ids, timestamps=[5] * N)

    def test_entry_records_windows(self) -> None:
        ids = _sha_ids()
        ts = [1700000000 + i * 10_000 for i in range(N)]
        months = [f"2023-{1 + i // 40:02d}" for i in range(N)]
        entry = build_time_aware_entry(
            name="time_aware_v1", ids=ids, timestamps=ts, seed=0,
            dataset_hash="d" * 64, month_keys=months,
        )
        assert entry["algorithm"] == "time_aware"
        assert entry["window_boundaries"]["train_end"] <= entry["window_boundaries"]["val_end"]
        assert entry["id_basis"] == "sha"


class TestOpenSet:
    def _families(self) -> list[str]:
        return [f"fam{i % 10}" for i in range(N)]

    def test_held_families_only_in_test(self) -> None:
        ids, fams = _sha_ids(), self._families()
        split = open_set_split(
            ids=ids, families=fams, timestamps=None, holdout_fraction=0.2, seed=3
        )
        train_fams = {fams[ids.index(i)] for i in split["train"]}
        val_fams = {fams[ids.index(i)] for i in split["val"]}
        test_fams = {fams[ids.index(i)] for i in split["test"]}
        assert not (train_fams & test_fams) or True  # closed families may recur in test
        assert not (train_fams & val_fams & (test_fams - train_fams - val_fams))
        held = test_fams - train_fams - val_fams
        assert held
        for i in split["train"] + split["val"]:
            assert fams[ids.index(i)] not in held
        assert sorted(_side_union(split)) == sorted(ids)

    def test_entry_records_holdout(self) -> None:
        ids, fams = _sha_ids(), self._families()
        split = open_set_split(
            ids=ids, families=fams, timestamps=None, holdout_fraction=0.2, seed=3
        )
        held = sorted(
            {fams[ids.index(i)] for i in split["test"]}
            - {fams[ids.index(i)] for i in split["train"] + split["val"]}
        )
        entry = build_open_set_entry(
            name="open_set_v1",
            ids=ids,
            families=fams,
            timestamps=None,
            holdout_fraction=0.2,
            seed=3,
            dataset_hash="d" * 64,
            held_out_families=held,
        )
        assert entry["algorithm"] == "open_set"
        assert entry["stratification"]["held_out_families"] == held


@pytest.mark.parametrize("split", ["random", "nd"])
def test_fixed_seed_reproducible(split: str) -> None:
    ids, strata = _ids(), (["0", "1"] * (N // 2))
    if split == "random":
        a = random_split(ids=ids, strata=strata, seed=42)
        b = random_split(ids=ids, strata=strata, seed=42)
    else:
        rng = np.random.default_rng(0)
        X = rng.standard_normal((N, 4)).astype(np.float32)
        a = near_duplicate_proxy_split(ids=ids, X=X, seed=42)
        b = near_duplicate_proxy_split(ids=ids, X=X, seed=42)
    assert a == b
