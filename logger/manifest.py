"""Dataset manifest (ADR-009): tracked provenance for immutable raw data.

``datasets/MANIFEST.json`` is tracked in git and contains **no data** — only
per-file metadata and SHA-256 hashes of files that live (gitignored) in
``datasets/raw/``. One entry per raw file:

- logical name, source URL, retrieval date, size, sha256, license/terms note
- for BODMAS feature archives: npz keys, shapes, dtypes, label meaning, and a
  verified row-to-sha256 mapping check

``dataset_hash`` — the value a run record carries — is the hash of the
canonical manifest entries a run uses, so a run is bound to the exact data
files it consumed. ``verify-data`` recomputes every hash and fails loudly on
any mismatch (acceptance test 2: a modified byte is detected). Raw files are
never modified by this module.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from logger.hashing import hash_file, hash_object

MANIFEST_PATH = Path("datasets/MANIFEST.json")
RAW_DIR = Path("datasets/raw")

MANDATORY_ENTRY_FIELDS = (
    "logical_name",
    "source_url",
    "retrieval_date",
    "size_bytes",
    "sha256",
    "license_note",
)


class ManifestError(RuntimeError):
    """Raised when the manifest is malformed or verification fails."""


def load_manifest(path: str | Path | None = None) -> dict[str, Any]:
    """Load and shape-check the manifest; raises :class:`ManifestError`.

    ``path`` defaults to the module-level ``MANIFEST_PATH`` resolved at call
    time (so tests and CLIs can repoint it).
    """
    p = Path(path) if path is not None else MANIFEST_PATH
    if not p.is_file():
        raise ManifestError(f"manifest not found: {p} (create it before any run)")
    try:
        manifest = json.loads(p.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ManifestError(f"manifest is not valid JSON: {p}: {exc}") from exc
    if not isinstance(manifest, dict) or "files" not in manifest:
        raise ManifestError("manifest must be a mapping with a 'files' list")
    if not isinstance(manifest["files"], list):
        raise ManifestError("manifest 'files' must be a list")
    for i, entry in enumerate(manifest["files"]):
        if not isinstance(entry, dict):
            raise ManifestError(f"manifest entry {i} is not a mapping")
        missing = [k for k in MANDATORY_ENTRY_FIELDS if k not in entry]
        if missing:
            raise ManifestError(f"manifest entry {i} missing fields: {missing}")
        if "path" not in entry:
            raise ManifestError(f"manifest entry {i} missing 'path'")
    return manifest


def manifest_entries_for(entries: list[dict[str, Any]]) -> str:
    """Hash the canonical form of the manifest entries a run uses.

    This is the ``dataset_hash`` recorded in run records: it changes if any
    field of any used entry changes (size, sha256, license note, ...).
    """
    return hash_object(entries)


def dataset_hash(
    logical_names: list[str] | None = None, manifest_path: str | Path | None = None
) -> str:
    """``dataset_hash`` over the whole manifest or a subset by logical name.

    Unknown logical names raise — a run may never silently hash "some" of the
    data it claims to use.
    """
    manifest = load_manifest(manifest_path)
    files = manifest["files"]
    if logical_names is None:
        return manifest_entries_for(files)
    known = {e["logical_name"] for e in files}
    unknown = set(logical_names) - known
    if unknown:
        raise ManifestError(f"unknown logical_name(s) in manifest: {sorted(unknown)}")
    used = [e for e in files if e["logical_name"] in set(logical_names)]
    return manifest_entries_for(used)


def resolve_raw_path(entry: dict[str, Any], raw_dir: str | Path | None = None) -> Path:
    """Resolve an entry's tracked relative path inside the raw dir.

    Rejects absolute paths and traversal outside ``raw_dir`` — the manifest
    describes files under ``datasets/raw/`` and nothing else.
    """
    rel = Path(entry["path"])
    if rel.is_absolute():
        raise ManifestError(f"entry {entry['logical_name']!r}: absolute paths not allowed")
    base = Path(RAW_DIR if raw_dir is None else raw_dir).resolve()
    full = (base / rel).resolve()
    if base not in full.parents:
        raise ManifestError(f"entry {entry['logical_name']!r}: path escapes datasets/raw/")
    return full


def verify_entry(entry: dict[str, Any], raw_dir: str | Path | None = None) -> None:
    """Recompute one entry's hash and size; raise :class:`ManifestError` on mismatch.

    A modified byte anywhere in the file changes the SHA-256, so any tampering
    or corruption is detected (acceptance test 2).
    """
    path = resolve_raw_path(entry, raw_dir)
    if not path.is_file():
        raise ManifestError(
            f"{entry['logical_name']}: raw file missing: {path} "
            "(data lives in gitignored datasets/raw/ — retrieve it per the manifest)"
        )
    actual_size = path.stat().st_size
    if actual_size != entry["size_bytes"]:
        raise ManifestError(
            f"{entry['logical_name']}: size mismatch "
            f"(manifest {entry['size_bytes']}, actual {actual_size})"
        )
    actual_sha = hash_file(path)
    if actual_sha != entry["sha256"]:
        raise ManifestError(
            f"{entry['logical_name']}: SHA-256 MISMATCH "
            f"(manifest {entry['sha256']}, actual {actual_sha}) — "
            "the raw file differs from what the manifest recorded"
        )


def verify_data(
    logical_names: list[str] | None = None,
    manifest_path: str | Path | None = None,
    raw_dir: str | Path | None = None,
) -> list[str]:
    """Verify all (or selected) manifest entries; return verified logical names.

    Fails loudly (raises :class:`ManifestError`) on the first mismatch. Raw
    files are only ever read.
    """
    manifest = load_manifest(manifest_path)
    entries = manifest["files"]
    if logical_names is not None:
        known = {e["logical_name"] for e in entries}
        unknown = set(logical_names) - known
        if unknown:
            raise ManifestError(f"unknown logical_name(s) in manifest: {sorted(unknown)}")
        wanted = set(logical_names)
        entries = [e for e in entries if e["logical_name"] in wanted]
    verified: list[str] = []
    for entry in entries:
        verify_entry(entry, raw_dir)
        verified.append(entry["logical_name"])
    return verified


def _describe_npz(path: str | Path) -> dict[str, Any]:
    """Describe an .npz archive's keys, shapes, dtypes — for manifest entries.

    Read-only; requires numpy (already pinned). No label values are read into
    the manifest, only structure — contents never enter git.
    """
    import numpy as np

    arrays: dict[str, Any] = {}
    with np.load(Path(path), allow_pickle=False) as zf:
        for key in sorted(zf.files):
            arr = zf[key]
            arrays[key] = {
                "shape": list(arr.shape),
                "dtype": arr.dtype.str,
                "size_bytes": int(arr.nbytes),
            }
    return {"npz_keys": arrays}


def make_entry(
    *,
    logical_name: str,
    path: str | Path,
    source_url: str,
    retrieval_date: str,
    license_note: str,
    raw_dir: str | Path | None = None,
    npz_description: bool = False,
) -> dict[str, Any]:
    """Build one manifest entry by hashing an existing raw file (read-only).

    Used at ingestion time to *create* the manifest; verification later
    recomputes the same fields. Never writes to the raw file. The stored
    ``path`` is relative to ``raw_dir`` (absolute inputs are relativized;
    paths outside ``raw_dir`` are rejected).
    """
    base = Path(RAW_DIR if raw_dir is None else raw_dir).resolve()
    given = Path(path)
    if given.is_absolute():
        try:
            rel_str = given.resolve().relative_to(base).as_posix()
        except ValueError as exc:
            raise ManifestError(f"entry {logical_name!r}: path escapes datasets/raw/") from exc
    else:
        rel_str = given.as_posix()
    p = resolve_raw_path({"logical_name": logical_name, "path": rel_str}, raw_dir)
    if not p.is_file():
        raise ManifestError(f"cannot manifest missing raw file: {p}")
    entry: dict[str, Any] = {
        "logical_name": logical_name,
        "path": rel_str,
        "source_url": source_url,
        "retrieval_date": retrieval_date,
        "size_bytes": p.stat().st_size,
        "sha256": hash_file(p),
        "license_note": license_note,
    }
    if npz_description:
        entry["structure"] = _describe_npz(p)
    return entry


def main(argv: list[str] | None = None) -> int:
    """``verify-data`` CLI: recompute all manifest hashes; fail loudly.

    Usage::

        python -m logger.manifest verify            # all entries
        python -m logger.manifest verify <name>...  # selected entries

    Exit codes: 0 verified, 1 mismatch/missing file, 2 usage error.
    """
    import sys

    args = list(sys.argv[1:] if argv is None else argv)
    if args and args[0] != "verify":
        print("usage: python -m logger.manifest verify [logical_name ...]", file=sys.stderr)
        return 2
    names = args[1:]
    try:
        verified = verify_data(names if names else None)
    except ManifestError as exc:
        print(f"verify-data FAILED: {exc}", file=sys.stderr)
        return 1
    if not verified:
        print("verify-data: no manifest entries (no raw data ingested yet)")
        return 0
    print(f"verify-data OK: {len(verified)} file(s) verified: {', '.join(verified)}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
