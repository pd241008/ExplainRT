"""Unit tests for logger.manifest (ADR-009).

Acceptance test 2 (prompt): ``verify-data`` detects a modified byte in a
fixture file. Uses synthetic fixture files in tmp_path — never real data
(hard rule, AGENTS.md §7).
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest
from logger.manifest import (
    ManifestError,
    dataset_hash,
    load_manifest,
    make_entry,
    manifest_entries_for,
    resolve_raw_path,
    verify_data,
)


def _write_fixture(raw_dir: Path, name: str, data: bytes) -> Path:
    raw_dir.mkdir(parents=True, exist_ok=True)
    p = raw_dir / name
    p.write_bytes(data)
    return p


def _entry_for(raw_dir: Path, name: str, data: bytes, **overrides: str) -> dict:
    p = _write_fixture(raw_dir, name, data)
    entry = {
        "logical_name": name,
        "path": name,
        "source_url": "https://example.invalid/bodmas",
        "retrieval_date": "2026-10-05",
        "size_bytes": len(data),
        "sha256": __import__("hashlib").sha256(data).hexdigest(),
        "license_note": "synthetic test fixture; no license",
    }
    entry.update(overrides)
    assert entry["sha256"]  # entry built from the actual bytes
    del p
    return entry


def _write_manifest(path: Path, entries: list[dict]) -> None:
    path.write_text(json.dumps({"schema_version": 1, "files": entries}), encoding="utf-8")


@pytest.fixture()
def manifest_env(tmp_path: Path) -> tuple[Path, Path, dict]:
    """(manifest_path, raw_dir, entry) with one verified synthetic file."""
    raw_dir = tmp_path / "raw"
    data = b"BODMAS-FEATURES-FIXTURE\x00\x01\x02"
    entry = _entry_for(raw_dir, "bodmas_v1.npz", data)
    manifest_path = tmp_path / "MANIFEST.json"
    _write_manifest(manifest_path, [entry])
    return manifest_path, raw_dir, entry


class TestLoadManifest:
    def test_load_valid(self, manifest_env: tuple[Path, Path, dict]) -> None:
        manifest_path, _, _ = manifest_env
        manifest = load_manifest(manifest_path)
        assert manifest["files"][0]["logical_name"] == "bodmas_v1.npz"

    def test_missing_manifest_raises(self, tmp_path: Path) -> None:
        with pytest.raises(ManifestError, match="not found"):
            load_manifest(tmp_path / "absent.json")

    def test_invalid_json_raises(self, tmp_path: Path) -> None:
        p = tmp_path / "MANIFEST.json"
        p.write_text("{not json", encoding="utf-8")
        with pytest.raises(ManifestError, match="not valid JSON"):
            load_manifest(p)

    def test_entry_missing_fields_raises(self, tmp_path: Path) -> None:
        p = tmp_path / "MANIFEST.json"
        _write_manifest(p, [{"logical_name": "x"}])
        with pytest.raises(ManifestError, match="missing fields"):
            load_manifest(p)


class TestVerifyData:
    def test_ok_file_verifies(self, manifest_env: tuple[Path, Path, dict]) -> None:
        manifest_path, raw_dir, _ = manifest_env
        assert verify_data(manifest_path=manifest_path, raw_dir=raw_dir) == ["bodmas_v1.npz"]

    def test_modified_byte_is_detected(self, manifest_env: tuple[Path, Path, dict]) -> None:
        """Acceptance test 2: flipping one byte fails verification loudly."""
        manifest_path, raw_dir, _ = manifest_env
        target = raw_dir / "bodmas_v1.npz"
        blob = bytearray(target.read_bytes())
        blob[0] ^= 0x01  # flip exactly one bit
        target.write_bytes(bytes(blob))
        with pytest.raises(ManifestError, match="SHA-256 MISMATCH"):
            verify_data(manifest_path=manifest_path, raw_dir=raw_dir)

    def test_size_change_is_detected(self, manifest_env: tuple[Path, Path, dict]) -> None:
        manifest_path, raw_dir, _ = manifest_env
        target = raw_dir / "bodmas_v1.npz"
        target.write_bytes(target.read_bytes() + b"trailing")
        with pytest.raises(ManifestError, match="size mismatch"):
            verify_data(manifest_path=manifest_path, raw_dir=raw_dir)

    def test_missing_raw_file_is_detected(self, manifest_env: tuple[Path, Path, dict]) -> None:
        manifest_path, raw_dir, _ = manifest_env
        (raw_dir / "bodmas_v1.npz").unlink()
        with pytest.raises(ManifestError, match="raw file missing"):
            verify_data(manifest_path=manifest_path, raw_dir=raw_dir)

    def test_subset_verification(self, tmp_path: Path) -> None:
        raw_dir = tmp_path / "raw"
        e1 = _entry_for(raw_dir, "a.bin", b"aaaa")
        e2 = _entry_for(raw_dir, "b.bin", b"bbbb")
        manifest_path = tmp_path / "MANIFEST.json"
        _write_manifest(manifest_path, [e1, e2])
        assert verify_data(["a.bin"], manifest_path=manifest_path, raw_dir=raw_dir) == ["a.bin"]
        with pytest.raises(ManifestError, match="unknown logical_name"):
            verify_data(["zzz.bin"], manifest_path=manifest_path, raw_dir=raw_dir)


class TestPathSafety:
    def test_absolute_path_rejected(self) -> None:
        with pytest.raises(ManifestError, match="absolute paths"):
            resolve_raw_path({"logical_name": "x", "path": "/etc/passwd"})

    def test_traversal_rejected(self) -> None:
        with pytest.raises(ManifestError, match="escapes"):
            resolve_raw_path({"logical_name": "x", "path": "../../etc/passwd"})


class TestDatasetHash:
    def test_changes_when_entry_changes(self, manifest_env: tuple[Path, Path, dict]) -> None:
        manifest_path, _, entry = manifest_env
        h = dataset_hash(manifest_path=manifest_path)
        changed = {**entry, "retrieval_date": "2026-10-06"}
        _write_manifest(manifest_path, [changed])
        assert dataset_hash(manifest_path=manifest_path) != h

    def test_subset_hash_stable(self, tmp_path: Path) -> None:
        raw_dir = tmp_path / "raw"
        e1 = _entry_for(raw_dir, "a.bin", b"aaaa")
        _entry_for(raw_dir, "b.bin", b"bbbb")
        manifest_path = tmp_path / "MANIFEST.json"
        _write_manifest(manifest_path, [e1, dict(_entry_for(raw_dir, "b.bin", b"bbbb"))])
        h = dataset_hash(["a.bin"], manifest_path=manifest_path)
        _write_manifest(manifest_path, [e1])
        assert dataset_hash(["a.bin"], manifest_path=manifest_path) == h


class TestNpzDescription:
    def test_npz_structure_recorded(self, tmp_path: Path) -> None:
        raw_dir = tmp_path / "raw"
        raw_dir.mkdir()
        p = raw_dir / "feat.npz"
        np.savez(
            p,
            X=np.arange(12, dtype=np.float32).reshape(3, 4),
            y=np.array([0, 1, 2], dtype=np.int64),
            timestamps=np.array([100, 200, 300], dtype=np.int64),
        )
        entry = make_entry(
            logical_name="bodmas_features",
            path=p,
            source_url="https://example.invalid",
            retrieval_date="2026-10-05",
            license_note="synthetic fixture",
            raw_dir=raw_dir,
            npz_description=True,
        )
        assert entry["structure"]["npz_keys"]["X"]["shape"] == [3, 4]
        assert entry["structure"]["npz_keys"]["X"]["dtype"] == "<f4"
        assert entry["structure"]["npz_keys"]["y"]["dtype"] == "<i8"
        assert manifest_entries_for([entry])
