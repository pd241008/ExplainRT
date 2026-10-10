"""Unit tests for bytelens.data.bodmas (ADR-010 §1).

Synthetic fixtures only — the real 250 MB npz is never touched by unit
tests (tests on real raw data are opt-in in test_bodmas_data.py, skipped
without the files).
"""

from __future__ import annotations

import hashlib
from pathlib import Path

import numpy as np
import pytest
from bytelens.data.bodmas import (
    BODMASDataError,
    DataMode,
    describe,
    load_bodmas,
    mint_npz_row_id,
)


@pytest.fixture(scope="module")
def npz_dir(tmp_path_factory) -> Path:
    """A tiny synthetic BODMAS-shaped npz (56 rows × 11 features)."""
    d = tmp_path_factory.mktemp("raw")
    rng = np.random.default_rng(0)
    X = rng.standard_normal((56, 11)).astype(np.float32)
    y = rng.integers(0, 2, 56).astype(np.int64)
    np.savez(d / "bodmas.npz", X=X, y=y)
    return d


class TestLoadNpz:
    def test_npz_only_mode(self, npz_dir: Path) -> None:
        data = load_bodmas(
            npz_path=npz_dir / "bodmas.npz",
            meta_path=npz_dir / "absent.csv",
            category_path=npz_dir / "absent2.csv",
            check_canonical_shape=False,
        )
        assert data.mode is DataMode.NPZ_ONLY
        assert data.n == 56 and data.d == 11
        assert set(np.unique(data.y).tolist()) <= {0, 1}
        assert np.isfinite(data.X).all()

    def test_missing_npz_raises(self, tmp_path: Path) -> None:
        with pytest.raises(BODMASDataError, match="not found"):
            load_bodmas(
                npz_path=tmp_path / "nope.npz",
                meta_path=tmp_path / "m.csv",
                category_path=tmp_path / "c.csv",
            )

    def test_bad_keys_rejected(self, npz_dir: Path) -> None:
        p = npz_dir / "bad_keys.npz"
        np.savez(p, features=np.zeros((4, 3)), labels=np.zeros(4))
        with pytest.raises(BODMASDataError, match="npz keys"):
            load_bodmas(
                npz_path=p,
                meta_path=npz_dir / "absent.csv",
                category_path=npz_dir / "absent2.csv",
                check_canonical_shape=False,
            )

    def test_non_finite_rejected(self, npz_dir: Path) -> None:
        p = npz_dir / "nan.npz"
        X = np.zeros((5, 3), dtype=np.float32)
        X[2, 1] = np.nan
        np.savez(p, X=X, y=np.zeros(5, dtype=np.int64))
        with pytest.raises(BODMASDataError, match="non-finite"):
            load_bodmas(
                npz_path=p,
                meta_path=npz_dir / "absent.csv",
                category_path=npz_dir / "absent2.csv",
                check_canonical_shape=False,
            )

    def test_non_binary_labels_rejected(self, npz_dir: Path) -> None:
        p = npz_dir / "labels.npz"
        np.savez(
            p,
            X=np.zeros((5, 3), dtype=np.float32),
            y=np.array([0, 1, 2, 0, 1], dtype=np.int64),
        )
        with pytest.raises(BODMASDataError, match="binary"):
            load_bodmas(
                npz_path=p,
                meta_path=npz_dir / "absent.csv",
                category_path=npz_dir / "absent2.csv",
                check_canonical_shape=False,
            )

    def test_shape_disagreement_rejected(self, npz_dir: Path) -> None:
        p = npz_dir / "shapes.npz"
        np.savez(p, X=np.zeros((5, 3), dtype=np.float32), y=np.zeros(7))
        with pytest.raises(BODMASDataError, match="disagree"):
            load_bodmas(
                npz_path=p,
                meta_path=npz_dir / "absent.csv",
                category_path=npz_dir / "absent2.csv",
                check_canonical_shape=False,
            )

    def test_canonical_shape_guard(self, npz_dir: Path) -> None:
        """The tiny synthetic npz must fail the canonical 134435×2381 check."""
        with pytest.raises(BODMASDataError, match="canonical"):
            load_bodmas(
                npz_path=npz_dir / "bodmas.npz",
                meta_path=npz_dir / "absent.csv",
                category_path=npz_dir / "absent2.csv",
                check_canonical_shape=True,
            )


class TestRowIds:
    def test_minted_ids_are_deterministic_and_stable(self, npz_dir: Path) -> None:
        a = mint_npz_row_id(0, "a" * 64)
        b = mint_npz_row_id(0, "a" * 64)
        c = mint_npz_row_id(1, "a" * 64)
        assert a == b and a != c
        assert len(a) == 64 and int(a, 16) >= 0

    def test_other_npz_yields_other_ids(self) -> None:
        assert mint_npz_row_id(0, "a" * 64) != mint_npz_row_id(0, "b" * 64)

    def test_row_ids_match_mint_formula(self, npz_dir: Path) -> None:
        data = load_bodmas(
            npz_path=npz_dir / "bodmas.npz",
            meta_path=npz_dir / "absent.csv",
            category_path=npz_dir / "absent2.csv",
            check_canonical_shape=False,
        )
        expected = hashlib.sha256(f"npz_row|3|{data.npz_sha256}".encode()).hexdigest()
        assert data.row_ids()[3] == expected


class TestDescribe:
    def test_no_samples_leak(self, npz_dir: Path) -> None:
        data = load_bodmas(
            npz_path=npz_dir / "bodmas.npz",
            meta_path=npz_dir / "absent.csv",
            category_path=npz_dir / "absent2.csv",
            check_canonical_shape=False,
        )
        desc = describe(data)
        blob = str(desc)
        assert "npz_only" in blob and desc["row_id_basis"] == "row_index"
        assert desc["label_counts"]["benign"] + desc["label_counts"]["malware"] == 56
        # Hashes only, never data values.
        assert data.X.tobytes() not in blob.encode()
