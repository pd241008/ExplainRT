"""Canonical hashing utilities (ADR-009).

One place defines how every provenance domain is hashed: file bytes, arrays,
resolved configs, split ID lists, manifests, and run-record chains. All hashes
are SHA-256. Canonical form for structured data is UTF-8 JSON with sorted
keys, no extra whitespace, and stable float formatting, so that two logically
identical inputs hash identically regardless of dict construction order or
float serialization quirks.

No fabrication: hashing never defaults or repairs inputs; a missing file or an
unsupported object is an error, not a hash of something else.
"""

from __future__ import annotations

import hashlib
import json
import math
import struct
from pathlib import Path
from typing import Any

CHUNK_SIZE = 1 << 20  # 1 MiB streaming chunks for large files


def canonical_json(obj: Any) -> str:
    """Serialize ``obj`` to the canonical JSON form used by every hash.

    Rules (ADR-009): sorted keys, UTF-8, no extra whitespace, and stable float
    formatting (finite floats via repr round-trip; NaN/Inf as strings, since
    JSON has no such literals and Python's json module would emit
    non-portable ``NaN``/``Infinity`` tokens).
    """
    return json.dumps(
        _normalize(obj),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
        default=_canonical_default,
    )


def _normalize(obj: Any) -> Any:
    """Pre-convert values json.dumps cannot handle natively.

    Called before serialization so that NaN/Inf floats become stable string
    sentinels (json's ``allow_nan=False`` raises before ``default`` is ever
    consulted) and NumPy scalars become plain Python numbers.
    """
    import numpy as np

    if isinstance(obj, dict):
        return {k: _normalize(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_normalize(v) for v in obj]
    if isinstance(obj, np.integer):
        return int(obj)
    if isinstance(obj, np.bool_):
        return bool(obj)
    if isinstance(obj, (float, np.floating)):
        return _stable_float(float(obj))
    return obj


def _canonical_default(obj: Any) -> Any:
    """JSON fallbacks for remaining non-native types; anything unknown is an error."""
    import numpy as np

    if isinstance(obj, np.ndarray):
        return {"__ndarray__": {"dtype": obj.dtype.str, "shape": list(obj.shape)}}
    if isinstance(obj, (set, frozenset)):
        return sorted(obj, key=repr)
    if isinstance(obj, Path):
        return obj.as_posix()
    raise TypeError(f"cannot canonicalize object of type {type(obj).__name__}")


def _stable_float(x: float) -> Any:
    """Stable, portable representation of a float for hashing."""
    if math.isnan(x):
        return "__nan__"
    if math.isinf(x):
        return "__inf__" if x > 0 else "__-inf__"
    return x


def _canonical_bytes(obj: Any) -> bytes:
    """Canonical UTF-8 bytes of ``obj`` (the thing that actually gets hashed)."""
    return canonical_json(obj).encode("utf-8")


def sha256_hex(data: bytes) -> str:
    """SHA-256 hex digest of ``data``."""
    return hashlib.sha256(data).hexdigest()


def hash_object(obj: Any) -> str:
    """SHA-256 of the canonical JSON form of ``obj``."""
    return sha256_hex(_canonical_bytes(obj))


def hash_file(path: str | Path) -> str:
    """SHA-256 of a file's raw bytes, streamed in chunks (large-file safe)."""
    p = Path(path)
    if not p.is_file():
        raise FileNotFoundError(f"cannot hash missing file: {p}")
    h = hashlib.sha256()
    with p.open("rb") as f:
        for chunk in iter(lambda: f.read(CHUNK_SIZE), b""):
            h.update(chunk)
    return h.hexdigest()


def hash_array(arr: Any) -> str:
    """SHA-256 of a NumPy array, including its dtype and shape.

    The canonical form binds dtype, shape, and raw little-endian bytes, so two
    arrays hash equal only if they are identical element-for-element under the
    same dtype and shape. Object arrays are rejected (their bytes are
    pointers, not data).
    """
    import numpy as np

    a = np.asarray(arr)
    if a.dtype.hasobject:
        raise TypeError("hash_array does not support object arrays")
    # '<' / '=' / '>' byte order made explicit little-endian, native 64-bit
    # platforms included, so the hash is stable across endianness conventions.
    canonical = a.astype(a.dtype.newbyteorder("<"), copy=False)
    h = hashlib.sha256()
    h.update(b"bytelens.array.v1")
    h.update(canonical.dtype.str.encode("ascii"))
    h.update(struct.pack("<Q", canonical.dtype.itemsize))
    h.update(struct.pack("<Q", len(canonical.shape)))
    for dim in canonical.shape:
        h.update(struct.pack("<Q", dim))
    h.update(np.ascontiguousarray(canonical).tobytes())
    return h.hexdigest()


def hash_config(resolved_cfg: Any) -> str:
    """SHA-256 of a **resolved** config.

    The input must already be resolved: YAML comments stripped by the parser,
    defaults merged, no ``None`` placeholders standing in for unset values.
    Hashing is order-insensitive and float-stable; any value change — even a
    one-bit float difference — changes the hash (acceptance test 1).
    """
    return hash_object(resolved_cfg)


def hash_split_ids(sorted_ids: list[str] | tuple[str, ...]) -> str:
    """SHA-256 of a sorted sample-ID list (ADR-009 split hash).

    The list must already be sorted and free of duplicates: this function is
    the identity of a split, so it is strict rather than normalizing. Adding,
    removing, or reordering an ID changes the hash (acceptance test 3).
    """
    ids = list(sorted_ids)
    if ids != sorted(ids):
        raise ValueError("hash_split_ids requires an already-sorted ID list")
    if len(set(ids)) != len(ids):
        raise ValueError("hash_split_ids requires a duplicate-free ID list")
    return hash_object(ids)
