"""Dataset loaders (bytelens/data).

Each dataset implements the ADR-008 adapter interface seam: raw files are
read-only, manifests verify bytes, and the loader is the only module that
opens them. Malware binaries are never touched here — this package reads
feature releases only (npz/csv); binaries stay out of scope until the
sandbox path is in play.
"""

from __future__ import annotations

from bytelens.data.bodmas import (
    BODMASData,
    DataMode,
    load_bodmas,
    mint_npz_row_id,
)

__all__ = ["BODMASData", "DataMode", "load_bodmas", "mint_npz_row_id"]
