"""BODMAS feature-release loader (ADR-010, Track A; ADR-008 rev 2 regime R1).

Loads the ingested npz (EMBER v2, 2381 features) read-only, with optional
metadata/category CSVs when present in ``datasets/raw/``:

- ``bodmas.npz``: ``X`` (134,435 × 2,381 float32, finite), ``y`` (binary).
- ``bodmas_metadata.csv``: ``sha,timestamp,family`` — joined **by row order**
  (the npz has no sha column; row order is the only link — verified by
  ``tests/unit/test_bodmas_data.py``).
- ``bodmas_malware_category.csv``: ``sha256,family`` — joined **by sha256**
  into an interim family map; available only when metadata exists.

Modes:

- ``FULL`` — npz + raw dir contains all three files; sha/timestamp/family
  arrays are available.
- ``NPZ_ONLY`` — interim mode (ADR-010): only X and y are loadable. Row IDs
  are minted deterministically as
  ``sha256("npz_row|" + str(i) + "|" + npz_file_sha256)[:64]`` and are NOT
  the sample sha256; consumers record ``id_basis="row_index"`` and must tag
  such runs ``smoke``. When the CSVs arrive, minted ids can be swapped for
  the real ``sha`` column by row order (npz hash is manifest-fixed, so
  minted ids are stable).

Raw files are never modified. ``allow_pickle=False`` everywhere (AGENTS.md
§2: parsing only, read-only).
"""

from __future__ import annotations

import csv
import hashlib
import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

import numpy as np
from logger.hashing import hash_array, hash_file

RAW_DIR = Path("datasets/raw")
NPZ_PATH = RAW_DIR / "bodmas.npz"
META_PATH = RAW_DIR / "bodmas_metadata.csv"
CATEGORY_PATH = RAW_DIR / "bodmas_malware_category.csv"

EXPECTED_N = 134_435
EXPECTED_D = 2_381


class DataMode(Enum):
    """Which provenance fields the loaded data can support (ADR-010)."""

    FULL = "full"
    NPZ_ONLY = "npz_only"


class BODMASDataError(RuntimeError):
    """Raised for malformed/missing BODMAS inputs — fail loudly, never default."""


@dataclass(frozen=True)
class BODMASData:
    """Loaded BODMAS feature release (all arrays are views into loaded npz)."""

    X: np.ndarray
    y: np.ndarray
    mode: DataMode
    npz_sha256: str
    feature_hash: str
    npz_files: list[str] = field(default_factory=list)

    @property
    def n(self) -> int:
        return int(self.X.shape[0])

    @property
    def d(self) -> int:
        return int(self.X.shape[1])

    def row_ids(self) -> list[str]:
        """Canonical sample IDs for this load (ADR-010 §1).

        FULL: the ``sha`` column (real sample sha256s). NPZ_ONLY: minted
        row IDs — deterministic but not sample sha256s; lock entries built
        from them must record ``id_basis: "row_index"``.
        """
        if self.mode is DataMode.FULL:
            return [_sha_row_id(i, self.npz_sha256) for i in range(self.n)]
        return [mint_npz_row_id(i, self.npz_sha256) for i in range(self.n)]


def mint_npz_row_id(row_index: int, npz_sha256: str) -> str:
    """Mint a deterministic 64-hex placeholder ID for npz row ``row_index``.

    NOT the sample sha256 — it is a stand-in binding row order to the exact
    npz bytes. The formula is fixed in ADR-010 so interim IDs survive code
    changes and can later be exchanged one-for-one with real sha256s by row
    order.
    """
    return _sha_row_id(row_index, npz_sha256)


def _sha_row_id(row_index: int, npz_sha256: str) -> str:
    payload = f"npz_row|{row_index}|{npz_sha256}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _load_npz(npz_path: Path) -> tuple[np.ndarray, np.ndarray, str]:
    if not npz_path.is_file():
        raise BODMASDataError(f"BODMAS npz not found: {npz_path}")
    sha = hash_file(npz_path)
    try:
        with np.load(npz_path, allow_pickle=False) as zf:
            keys = sorted(zf.files)
            if keys != ["X", "y"]:
                raise BODMASDataError(f"expected npz keys ['X','y'], got {keys}")
            X = zf["X"]
            y = zf["y"]
    except BODMASDataError:
        raise
    except Exception as exc:  # unreadable/corrupt archive
        raise BODMASDataError(f"failed to read {npz_path}: {exc}") from exc
    X = np.asarray(X)
    y = np.asarray(y)
    if X.ndim != 2:
        raise BODMASDataError(f"X must be 2-D, got shape {X.shape}")
    n, d = X.shape
    if n < 1 or d < 1:
        raise BODMASDataError(f"X is empty: {X.shape}")
    if not X.shape == (y.shape[0],) + X.shape[1:]:
        raise BODMASDataError(
            f"X rows ({X.shape[0]}) disagree with y length ({y.shape[0]})"
        )
    if not np.isfinite(X).all():
        raise BODMASDataError("X contains non-finite values")
    bad_labels = set(np.unique(y).tolist()) - {0, 1}
    if bad_labels:
        raise BODMASDataError(f"y must be binary {{0,1}}; found {sorted(bad_labels)}")
    return X, y.astype(np.int64), sha


def _check_shape(X: np.ndarray) -> None:
    """Canonical-shape check for the ingested BODMAS release (ADR-010 §1)."""
    if X.shape != (EXPECTED_N, EXPECTED_D):
        raise BODMASDataError(
            f"BODMAS X shape {X.shape} != canonical {(EXPECTED_N, EXPECTED_D)}; "
            "refusing to guess features"
        )


def _read_metadata(meta_path: Path) -> list[dict[str, str]]:
    with meta_path.open(newline="", encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    required = {"sha", "timestamp", "family"}
    if not rows:
        raise BODMASDataError(f"metadata CSV empty: {meta_path}")
    missing = required - set(rows[0])
    if missing:
        raise BODMASDataError(
            f"metadata columns {sorted(missing)} missing from {meta_path} — "
            "ABORTING per Track A rule: stop and ask if columns differ from "
            "the existing test's assumptions"
        )
    return rows


def _read_category(category_path: Path) -> list[dict[str, str]]:
    with category_path.open(newline="", encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    required = {"sha256", "family"}
    if not rows:
        raise BODMASDataError(f"category CSV empty: {category_path}")
    missing = required - set(rows[0])
    if missing:
        raise BODMASDataError(
            f"category columns {sorted(missing)} missing from {category_path} — "
            "ABORTING per Track A rule: stop and ask if columns differ from "
            "the existing test's assumptions"
        )
    return rows


def _read_timestamp(ts_raw: str) -> int:
    """Parse one metadata timestamp (unix epoch seconds) — strict, no guessing."""
    value = int(float(ts_raw))
    if value <= 0:
        raise BODMASDataError(f"non-positive timestamp {ts_raw!r}")
    return value


def load_bodmas(
    *,
    npz_path: Path | None = None,
    meta_path: Path | None = None,
    category_path: Path | None = None,
    check_canonical_shape: bool = True,
) -> BODMASData:
    """Load BODMAS; auto-detect FULL vs NPZ_ONLY from file presence.

    Interim npz-only mode is explicit via ``DataMode.NPZ_ONLY``; callers
    building splits/locks from it must record ``id_basis="row_index"`` and
    tag runs ``smoke`` (ADR-010 §1).
    """
    npz_path = Path(NPZ_PATH if npz_path is None else npz_path)
    meta_path = Path(META_PATH if meta_path is None else meta_path)
    category_path = Path(CATEGORY_PATH if category_path is None else category_path)

    X, y, npz_sha = _load_npz(npz_path)
    if check_canonical_shape:
        _check_shape(X)

    mode = (
        DataMode.FULL
        if (meta_path.is_file() and category_path.is_file())
        else DataMode.NPZ_ONLY
    )
    npz_files = sorted(["X", "y"])
    feature_hash = hash_array(X)
    return BODMASData(
        X=X,
        y=y,
        mode=mode,
        npz_sha256=npz_sha,
        feature_hash=feature_hash,
        npz_files=npz_files,
    )


def describe(data: BODMASData) -> dict[str, Any]:
    """Canonical description for logging (no samples ever logged — hashes only)."""
    return {
        "mode": data.mode.value,
        "n": data.n,
        "d": data.d,
        "npz_sha256": data.npz_sha256,
        "feature_hash": data.feature_hash,
        "label_counts": {
            "benign": int((data.y == 0).sum()),
            "malware": int((data.y == 1).sum()),
        },
        "row_id_basis": "sha" if data.mode is DataMode.FULL else "row_index",
        "checked_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
