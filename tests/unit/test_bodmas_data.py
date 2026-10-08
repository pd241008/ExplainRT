"""Sanity checks on the ingested BODMAS feature release (opt-in: needs raw data).

Skipped when ``datasets/raw/`` has no data (CI carries none). Reads only; feature
arrays and CSVs are never modified, and ``allow_pickle`` stays off.
"""

from __future__ import annotations

import csv
from pathlib import Path

import numpy as np
import pytest
from logger.manifest import verify_data

RAW = Path("datasets/raw")
NPZ = RAW / "bodmas.npz"
META = RAW / "bodmas_metadata.csv"
CATEGORY = RAW / "bodmas_malware_category.csv"

pytestmark = pytest.mark.skipif(
    not (NPZ.is_file() and META.is_file() and CATEGORY.is_file()),
    reason="BODMAS raw feature files not present in datasets/raw/",
)


@pytest.fixture(scope="module")
def y() -> np.ndarray:
    with np.load(NPZ, allow_pickle=False) as zf:
        return zf["y"]


@pytest.fixture(scope="module")
def metadata() -> list[dict[str, str]]:
    with META.open(newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


@pytest.fixture(scope="module")
def category() -> list[dict[str, str]]:
    with CATEGORY.open(newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def test_manifest_hashes_match() -> None:
    assert verify_data() == ["bodmas_features", "bodmas_metadata", "bodmas_malware_category"]


def test_npz_structure() -> None:
    with np.load(NPZ, allow_pickle=False) as zf:
        assert sorted(zf.files) == ["X", "y"]
        assert zf["X"].shape == (134_435, 2_381)
        assert zf["X"].dtype == np.float32
        assert np.isfinite(zf["X"]).all()
        assert zf["y"].shape == (134_435,)


def test_labels_are_binary(y: np.ndarray) -> None:
    assert set(np.unique(y).tolist()) == {0, 1}
    assert int((y == 1).sum()) == 57_293
    assert int((y == 0).sum()) == 77_142


def test_metadata_rows_align_with_labels(y: np.ndarray, metadata: list[dict[str, str]]) -> None:
    # npz has no sha column; row order is the only link. Malware rows carry a family,
    # benign rows do not, so label and family-presence must agree on every row.
    assert len(metadata) == len(y)
    has_family = np.array([1 if r["family"] else 0 for r in metadata])
    assert (has_family == y).all()


def test_metadata_shas_unique_and_time_sorted(metadata: list[dict[str, str]]) -> None:
    shas = [r["sha"] for r in metadata]
    assert len(set(shas)) == len(shas)
    stamps = [r["timestamp"] for r in metadata]
    assert all(stamps)
    assert stamps == sorted(stamps)


def test_category_shas_are_the_malware_rows(
    y: np.ndarray, metadata: list[dict[str, str]], category: list[dict[str, str]]
) -> None:
    # Category file is in a different row order, so join by sha, never by position.
    malware_shas = {r["sha"] for r, label in zip(metadata, y, strict=True) if label == 1}
    category_shas = [r["sha256"] for r in category]
    assert len(set(category_shas)) == len(category_shas)
    assert set(category_shas) == malware_shas
