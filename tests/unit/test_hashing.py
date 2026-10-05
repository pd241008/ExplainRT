"""Unit tests for logger.hashing (ADR-009).

Acceptance test 1 (prompt): hash stability — the same config in different key
order gives the same ``config_hash``; any value change gives a different one.
Also covers file/array/split hashing invariants used by every later domain.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest
from logger.hashing import (
    canonical_json,
    hash_array,
    hash_config,
    hash_file,
    hash_object,
    hash_split_ids,
)

CONFIG = {"model": "malconv", "seed": 42, "render": {"width_bucket": 224}}


class TestCanonicalJson:
    def test_key_order_independent(self) -> None:
        assert canonical_json({"a": 1, "b": 2}) == canonical_json({"b": 2, "a": 1})

    def test_no_whitespace_utf8(self) -> None:
        assert canonical_json({"k": "ä"}) == '{"k":"ä"}'

    def test_stable_float_formatting(self) -> None:
        assert canonical_json({"x": 0.1 + 0.2}) == canonical_json({"x": 0.30000000000000004})

    def test_nan_and_inf_are_representable(self) -> None:
        assert "__nan__" in canonical_json({"x": float("nan")})
        assert "__inf__" in canonical_json({"x": float("inf")})

    def test_unsupported_type_raises(self) -> None:
        with pytest.raises(TypeError):
            canonical_json({"x": object()})

    def test_round_trip_survives_key_order(self) -> None:
        import json

        a = json.loads(canonical_json(CONFIG))
        b = json.loads(canonical_json(dict(reversed(list(CONFIG.items())))))
        assert a == b


class TestConfigHash:
    def test_same_config_different_key_order_same_hash(self) -> None:
        reordered = {
            "render": {"width_bucket": 224},
            "seed": 42,
            "model": "malconv",
        }
        assert hash_config(CONFIG) == hash_config(reordered)

    def test_any_value_change_changes_hash(self) -> None:
        base = hash_config(CONFIG)
        assert hash_config({**CONFIG, "seed": 43}) != base
        assert hash_config({**CONFIG, "model": "cnn"}) != base
        assert hash_config({**CONFIG, "render": {"width_bucket": 256}}) != base
        assert hash_config({**CONFIG, "extra": 1}) != base
        # Even a one-ULP float change must register.
        assert hash_config({"x": 1.0}) != hash_config({"x": np.nextafter(1.0, 2.0)})

    def test_deterministic_and_hex(self) -> None:
        h = hash_config(CONFIG)
        assert h == hash_config(CONFIG)
        assert len(h) == 64
        int(h, 16)


class TestHashFile:
    def test_matches_known_sha256(self, tmp_path: Path) -> None:
        p = tmp_path / "blob.bin"
        p.write_bytes(b"hello world")
        # sha256("hello world"), independently computed.
        assert hash_file(p) == ("b94d27b9934d3e08a52e52d7da7dabfac484efe37a5380ee9088f7ace2efcde9")

    def test_large_file_streamed(self, tmp_path: Path) -> None:
        # > 2 chunks at 1 MiB to exercise the streaming loop.
        p = tmp_path / "big.bin"
        data = bytes(range(256)) * (2**21 // 256 + 7)
        p.write_bytes(data)
        import hashlib

        assert hash_file(p) == hashlib.sha256(data).hexdigest()

    def test_missing_file_raises(self, tmp_path: Path) -> None:
        with pytest.raises(FileNotFoundError):
            hash_file(tmp_path / "nope.bin")

    def test_empty_file_hashes(self, tmp_path: Path) -> None:
        p = tmp_path / "empty.bin"
        p.write_bytes(b"")
        import hashlib

        assert hash_file(p) == hashlib.sha256(b"").hexdigest()


class TestHashArray:
    def test_includes_dtype_and_shape(self) -> None:
        a = np.array([1, 2, 3], dtype=np.int64)
        assert hash_array(a) != hash_array(a.astype(np.int32))
        assert hash_array(a) != hash_array(a.reshape(1, 3))
        assert hash_array(a) != hash_array(a[:-1])

    def test_equal_arrays_hash_equal(self) -> None:
        assert hash_array(np.arange(10)) == hash_array(np.arange(10))

    def test_value_change_changes_hash(self) -> None:
        a = np.arange(10, dtype=np.float64)
        b = a.copy()
        b[3] = np.nextafter(b[3], np.inf)
        assert hash_array(a) != hash_array(b)

    def test_nan_positions_matter(self) -> None:
        a = np.array([1.0, np.nan, 3.0])
        b = np.array([1.0, 3.0, np.nan])
        assert hash_array(a) != hash_array(b)

    def test_endianness_stable(self) -> None:
        a = np.arange(4, dtype=">i8")
        b = np.arange(4, dtype="<i8")
        assert hash_array(a) == hash_array(b)

    def test_object_arrays_rejected(self) -> None:
        with pytest.raises(TypeError):
            hash_array(np.array([{"a": 1}], dtype=object))


class TestHashObject:
    def test_ndarray_default_is_hashable(self) -> None:
        assert hash_object({"arr": np.arange(3)}) == hash_object({"arr": np.arange(3)})

    def test_sets_are_order_stable(self) -> None:
        assert hash_object({"s": {3, 1, 2}}) == hash_object({"s": {2, 3, 1}})


class TestHashSplitIds:
    def test_sorted_list_is_stable(self) -> None:
        ids = ["aa", "bb", "cc"]
        assert hash_split_ids(ids) == hash_split_ids(list(ids))

    def test_add_remove_or_reorder_changes_hash(self) -> None:
        ids = ["aa", "bb", "cc"]
        h = hash_split_ids(ids)
        assert hash_split_ids(["aa", "bb", "cc", "dd"]) != h
        assert hash_split_ids(["aa", "cc"]) != h
        # Different order is a different split; strictness enforced below.
        with pytest.raises(ValueError, match="sorted"):
            hash_split_ids(["bb", "aa", "cc"])

    def test_duplicates_rejected(self) -> None:
        with pytest.raises(ValueError, match="duplicate"):
            hash_split_ids(["aa", "aa"])
