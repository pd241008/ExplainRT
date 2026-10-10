"""Unit tests for bytelens.eval.subsets (ADR-010 §3)."""

from __future__ import annotations

import numpy as np
import pytest
from bytelens.data.bodmas import mint_npz_row_id
from bytelens.eval.subsets import (
    MIN_STRATUM,
    build_subset_entry,
    stratified_subset,
    subset_strata_npzonly,
)

N = 200


def _ids() -> list[str]:
    return [mint_npz_row_id(i, "b" * 64) for i in range(N)]


class TestStratifiedSubset:
    def test_deterministic(self) -> None:
        ids, strata = _ids(), (["0", "1"] * (N // 2))
        a, ca = stratified_subset(ids=ids, strata=strata, seed=5, min_stratum=0)
        b, cb = stratified_subset(ids=ids, strata=strata, seed=5, min_stratum=0)
        assert a == b and ca == cb

    def test_takes_10pct_per_stratum(self) -> None:
        ids, strata = _ids(), (["0", "1"] * (N // 2))
        picked, counts = stratified_subset(ids=ids, strata=strata, seed=5, min_stratum=0)
        assert len(picked) == 20  # 10 per stratum: 100 × 0.10 = 10
        assert counts == {"0": 10, "1": 10}

    def test_min_stratum_keeps_one(self) -> None:
        """Tiny strata keep ≥1 sample and are recorded, never dropped."""
        ids = _ids()
        strata = ["small"] + ["big"] * (N - 1)
        picked, counts = stratified_subset(ids=ids, strata=strata, seed=1, min_stratum=MIN_STRATUM)
        assert "small" in counts and counts["small"] >= 1
        assert counts["big"] == int(round(0.10 * (N - 1)))

    def test_seed_matters(self) -> None:
        ids, strata = _ids(), (["0", "1"] * (N // 2))
        a, _ = stratified_subset(ids=ids, strata=strata, seed=1, min_stratum=0)
        b, _ = stratified_subset(ids=ids, strata=strata, seed=2, min_stratum=0)
        assert a != b

    def test_bad_fraction(self) -> None:
        with pytest.raises(ValueError, match="fraction"):
            stratified_subset(ids=_ids(), strata=["0"] * N, seed=0, fraction=0.0)

    def test_npzonly_strata_shape(self) -> None:
        rng = np.random.default_rng(0)
        X = rng.standard_normal((N, 6)).astype(np.float32)
        y = (rng.random(N) > 0.5).astype(np.int64)
        strata = subset_strata_npzonly(y, X, seed=0)
        assert len(strata) == N
        assert all(s[0] in "01" for s in strata)


class TestSubsetEntry:
    def test_entry_records_fraction_and_stratification(self) -> None:
        ids, strata = _ids(), (["0", "1"] * (N // 2))
        picked, _ = stratified_subset(ids=ids, strata=strata, seed=5, min_stratum=0)
        entry = build_subset_entry(
            name="pilot_10pct_npzonly",
            ids=ids,
            strata=strata,
            seed=5,
            dataset_hash="d" * 64,
        )
        # build_subset_entry samples internally; contexts differ from picked.
        picked2, _ = stratified_subset(ids=ids, strata=strata, seed=5, min_stratum=0)
        assert entry["sampling_fraction"] == 0.10
        assert entry["stratification"]["by"] == ["label", "feature_bucket"]
        assert entry["counts"]["test"] == len(picked2)
        assert entry["id_basis"] == "row_index"
