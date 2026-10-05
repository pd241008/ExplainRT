"""Structured run records (AGENTS.md section 8; ADR-007; ADR-009).

One record per run. The record is the only path by which a number may reach
the paper, README, or an ADR (hard rule, AGENTS.md section 2).

ADR-009 additions over ADR-007 (schema_version 2):

- **Derived run ID** — ``run_id = sha256(config_hash | dataset_hash |
  split_hash | git_sha | seed)[:12]``; the UTC timestamp is stored separately
  in ``created``. Identical inputs give identical run IDs (acceptance test 4).
- **Full provenance** — full resolved config, git dirty flag (plus a hash of
  ``git diff`` when dirty), branch, environment (Python/frameworks/CUDA/
  hardware, requirements hash, sandbox image), all seeds + determinism flags,
  tags, ``test_touched`` and its lock, model artifact sha256.
- **Hash chain** — each appended record carries the previous record's
  ``record_hash``; its own ``record_hash`` is the SHA-256 of the canonical
  record without that field. Editing or deleting a line breaks the chain and
  is detected by :func:`verify_chain` (acceptance test 5). Append-only:
  writers never rewrite history.

No fabricated fields: anything unavailable (git, GPU, sandbox digest) is
recorded as ``null``, never invented.
"""

from __future__ import annotations

import json
import platform
import subprocess
import sys
import time
from dataclasses import asdict, dataclass, field, fields
from pathlib import Path
from typing import Any

from logger.hashing import hash_file, hash_object, sha256_hex

SCHEMA_VERSION = 2

REQUIRED_FIELDS = (
    "run_id",
    "created",
    "config_hash",
    "config",
    "git_sha",
    "seed",
    "dataset_split_hash",
    "model_name",
    "metrics",
    "wall_time_sec",
    "hardware",
    "requirements_hash",
)


def config_hash(config: dict[str, Any]) -> str:
    """Stable SHA-256 of a config dict, independent of key order."""
    return hash_object(config)


def derivable_run_id(
    config_hash: str | None,
    dataset_hash: str | None,
    split_hash: str | None,
    git_sha: str | None,
    seed: int,
) -> str:
    """Run ID derived from the run's identity inputs (ADR-009).

    ``sha256(config_hash | dataset_hash | split_hash | git_sha | seed)[:12]``
    with ``|`` as the component separator; unavailable components contribute
    the empty string so derivation never fails and never guesses.
    """
    joined = "|".join(
        [
            config_hash or "",
            dataset_hash or "",
            split_hash or "",
            git_sha or "",
            str(seed),
        ]
    )
    return sha256_hex(joined.encode("utf-8"))[:12]


def compute_record_hash(record_without_hash: dict[str, Any]) -> str:
    """SHA-256 of the canonical record without its ``record_hash`` field."""
    body = {k: v for k, v in record_without_hash.items() if k != "record_hash"}
    return hash_object(body)


# ── Git context ─────────────────────────────────────────────────────────────


def _run_git(args: list[str], cwd: Path | None) -> str | None:
    """Run one git command; return stdout or None on any failure (no guessing)."""
    try:
        out = subprocess.run(
            ["git", *args],
            capture_output=True,
            text=True,
            check=True,
            cwd=cwd,
        )
    except (OSError, subprocess.CalledProcessError):
        return None
    return out.stdout


def git_status(repo_dir: Path | None = None) -> dict[str, Any]:
    """Git working-tree context: sha, branch, dirty flag, diff hash.

    ``git_diff_hash`` is SHA-256 over ``git diff HEAD`` output plus the
    porcelain status listing (so tracked edits and staged/untracked presence
    are both captured); ``None`` outside a git repo or when the diff is
    unavailable.
    """
    sha = _run_git(["rev-parse", "HEAD"], repo_dir)
    if sha is None:
        return {"git_sha": None, "branch": None, "git_dirty": None, "git_diff_hash": None}
    branch = _run_git(["rev-parse", "--abbrev-ref", "HEAD"], repo_dir)
    status = _run_git(["status", "--porcelain"], repo_dir)
    diff = _run_git(["diff", "HEAD"], repo_dir)
    dirty = bool(status and status.strip())
    diff_hash = None
    if dirty and diff is not None and status is not None:
        diff_hash = sha256_hex((diff + status).encode("utf-8"))
    return {
        "git_sha": sha.strip(),
        "branch": branch.strip() if branch is not None else None,
        "git_dirty": dirty,
        "git_diff_hash": diff_hash,
    }


def _requirements_hash(repo_dir: Path | None) -> str | None:
    """SHA-256 of requirements.txt, or None when the file is absent."""
    req = Path("requirements.txt") if repo_dir is None else Path(repo_dir) / "requirements.txt"
    if not req.is_file():
        return None
    return hash_file(req)


def _framework_versions() -> dict[str, str | None]:
    """Pinned framework versions via importlib.metadata; absent → null."""
    from importlib.metadata import version

    out: dict[str, str | None] = {}
    for dist in ("numpy", "torch", "lightgbm", "scipy", "pandas"):
        try:
            out[dist] = version(dist)
        except Exception:  # package not installed in this environment
            out[dist] = None
    return out


def _cuda_info() -> dict[str, Any] | None:
    """CUDA runtime info via torch when available; None otherwise."""
    try:
        import torch
    except ImportError:
        return None
    info: dict[str, Any] = {"available": bool(torch.cuda.is_available())}
    if torch.cuda.is_available():
        info["cuda_version"] = getattr(torch.version, "cuda", None)
        info["device_count"] = torch.cuda.device_count()
    return info


def _sandbox_image() -> str | None:
    """Sandbox image digest if the run happened inside one (env-provided)."""
    import os

    return os.environ.get("BYTELENS_SANDBOX_IMAGE")


def capture_env(repo_dir: Path | None = None) -> dict[str, Any]:
    """Capture the execution environment for a run record.

    Never estimates: missing values (git, GPU, sandbox) are null.
    """
    del repo_dir  # reserved for explicit repo discovery; git lookup uses cwd
    return {
        "python": sys.version.split()[0],
        "platform": platform.platform(),
        "machine": platform.machine(),
        "cpu_count": None if platform.system() == "unknown" else _cpu_count(),
        "gpu": _gpu(),
        "frameworks": _framework_versions(),
        "cuda": _cuda_info(),
        "requirements_hash": _requirements_hash(Path.cwd()),
        "sandbox_image": _sandbox_image(),
    }


def _cpu_count() -> int | None:
    try:
        import os

        return os.cpu_count()
    except Exception:  # pragma: no cover - defensive, never crash a run
        return None


def _gpu() -> list[dict[str, Any]] | None:
    """GPU inventory via torch when available; None otherwise (no guessing)."""
    try:
        import torch  # type: ignore[import-untyped]
    except ImportError:
        return None
    if not torch.cuda.is_available():
        return []
    return [
        {"name": torch.cuda.get_device_name(i), "capability": None}
        for i in range(torch.cuda.device_count())
    ]


def expand_seeds(seed: int, framework_seed: int | None = None) -> dict[str, int]:
    """All seeds for a run: python/numpy get ``seed``; framework defaults to it."""
    return {
        "python": int(seed),
        "numpy": int(seed),
        "framework": int(framework_seed) if framework_seed is not None else int(seed),
    }


@dataclass
class RunRecord:
    """One experiment run: identity, inputs, metrics, environment, chain."""

    run_id: str
    created: str
    config_hash: str
    config: dict[str, Any]
    git_sha: str | None
    seed: int
    dataset_split_hash: str | None
    model_name: str
    metrics: dict[str, float] = field(default_factory=dict)
    wall_time_sec: float | None = None
    hardware: dict[str, Any] = field(default_factory=capture_env)
    requirements_hash: str | None = None
    # ── ADR-009 fields (schema v2) ──
    schema_version: int = SCHEMA_VERSION
    dataset_hash: str | None = None
    split_name: str | None = None
    tags: list[str] = field(default_factory=list)
    test_touched: bool = False
    test_lock_hash: str | None = None
    git_dirty: bool | None = None
    git_diff_hash: str | None = None
    branch: str | None = None
    seeds: dict[str, int] | None = None
    determinism: dict[str, Any] = field(default_factory=dict)
    model_artifact_sha256: str | None = None
    prev_record_hash: str | None = None
    record_hash: str | None = None

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["schema_version"] = SCHEMA_VERSION
        return d

    def body_dict(self) -> dict[str, Any]:
        """Record dict without ``record_hash`` — the chain-hash input."""
        body = self.to_dict()
        body.pop("record_hash", None)
        return body

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), sort_keys=True, separators=(",", ":"))

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> RunRecord:
        missing = [k for k in REQUIRED_FIELDS if k not in raw]
        if missing:
            raise ValueError(f"run record missing required fields: {missing}")
        known = {f.name for f in fields(cls)}
        unknown = [k for k in raw if k not in known]
        if unknown:
            raise ValueError(f"run record has unknown fields (newer schema?): {unknown}")
        rec = cls(**{k: raw[k] for k in known if k in raw})
        if rec.schema_version > SCHEMA_VERSION:
            raise ValueError(
                f"run record schema {rec.schema_version} is newer than this reader ({SCHEMA_VERSION})"
            )
        if rec.record_hash is not None:
            expected = compute_record_hash(rec.to_dict())
            if expected != rec.record_hash:
                raise ValueError(f"record_hash mismatch for run {rec.run_id}: record was modified")
        return rec

    def seal(self) -> str:
        """Compute and set ``record_hash`` from the record body; return it."""
        self.record_hash = compute_record_hash(self.body_dict())
        return self.record_hash


class RunRecorder:
    """Creates and persists run records as JSON Lines.

    Usage::

        rec = RunRecorder(output_dir).start(config=cfg, seed=42,
                                            model_name="malconv")
        ... run ...
        RunRecorder.finish(rec, metrics={...}, wall_time_sec=...)
        append_jsonl(rec, path)   # chains and seals, then appends
    """

    def __init__(self, output_dir: str | Path = "logger/runs") -> None:
        self.output_dir = Path(output_dir)

    def start(
        self,
        config: dict[str, Any],
        seed: int,
        model_name: str,
        dataset_hash: str | None = None,
        dataset_split_hash: str | None = None,
        split_name: str | None = None,
        tags: list[str] | None = None,
        test_touched: bool = False,
        test_lock_hash: str | None = None,
        determinism: dict[str, Any] | None = None,
        framework_seed: int | None = None,
        repo_dir: Path | None = None,
        existing_run_id: str | None = None,
    ) -> RunRecord:
        """Open a record at run start. ``metrics`` are filled by ``finish``.

        ``existing_run_id`` exists only for controlled test/replay callers
        that must reproduce a historical identity byte-for-byte; production
        code derives the ID from the inputs.
        """
        cfg_h = config_hash(config)
        git = git_status(repo_dir)
        env = capture_env()
        run_id = existing_run_id or derivable_run_id(
            cfg_h, dataset_hash, dataset_split_hash, git["git_sha"], seed
        )
        record = RunRecord(
            run_id=run_id,
            created=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            config_hash=cfg_h,
            config=config,
            git_sha=git["git_sha"],
            seed=seed,
            dataset_split_hash=dataset_split_hash,
            model_name=model_name,
            hardware=env,
            requirements_hash=env.get("requirements_hash"),
            dataset_hash=dataset_hash,
            split_name=split_name,
            tags=list(tags) if tags else [],
            test_touched=bool(test_touched),
            test_lock_hash=test_lock_hash,
            git_dirty=git["git_dirty"],
            git_diff_hash=git["git_diff_hash"],
            branch=git["branch"],
            seeds=expand_seeds(seed, framework_seed),
            determinism=dict(determinism) if determinism else {},
        )
        return record

    @staticmethod
    def finish(
        record: RunRecord,
        metrics: dict[str, float],
        wall_time_sec: float,
        model_artifact_sha256: str | None = None,
    ) -> RunRecord:
        record.metrics = dict(metrics)
        record.wall_time_sec = float(wall_time_sec)
        record.model_artifact_sha256 = model_artifact_sha256
        return record


def prev_record_hash(path: str | Path) -> str | None:
    """The ``record_hash`` of the last record in a JSONL file, or None if empty."""
    p = Path(path)
    if not p.is_file():
        return None
    last: str | None = None
    with p.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                last = line
    if last is None:
        return None
    rec = json.loads(last)
    return rec.get("record_hash")


def prepend_chain(record: RunRecord, path: str | Path) -> RunRecord:
    """Set ``prev_record_hash`` from the file's last record and seal the record."""
    record.prev_record_hash = prev_record_hash(path)
    record.seal()
    return record


def append_jsonl(record: RunRecord, path: str | Path) -> RunRecord:
    """Chain-seal and append one record as a JSON line (append-only).

    The record is mutated with ``prev_record_hash`` + ``record_hash`` and
    returned, so the caller can trace it. The file is opened in append mode:
    existing lines are never rewritten.
    """
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    prepend_chain(record, p)
    with p.open("a", encoding="utf-8") as f:
        f.write(record.to_json() + "\n")
    return record


def read_jsonl(path: str | Path, check_chain: bool = False) -> list[RunRecord]:
    """Read all records from a JSONL file. Skips blank lines.

    With ``check_chain=True`` the hash chain is checked while reading and a
    mismatch raises ``ValueError`` (tamper evidence, acceptance test 5).
    """
    records: list[RunRecord] = []
    with Path(path).open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            records.append(RunRecord.from_dict(json.loads(line)))
    if check_chain:
        errors = verify_chain(path)
        if errors:
            raise ValueError(f"hash chain broken in {path}: {errors[0]}")
    return records


def verify_chain(path: str | Path) -> list[str]:
    """Verify the hash chain of a JSONL record file; return a list of problems.

    For every record: ``record_hash`` must match the SHA-256 of the canonical
    record without it, and ``prev_record_hash`` must equal the previous
    record's ``record_hash``. An edited or deleted line therefore detects.
    Empty list = intact chain.
    """
    problems: list[str] = []
    prev_hash: str | None = None
    index = 0
    with Path(path).open(encoding="utf-8") as f:
        for raw in f:
            line = raw.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError as exc:
                problems.append(f"line {index}: not valid JSON: {exc}")
                break
            actual = compute_record_hash(rec)
            if rec.get("record_hash") != actual:
                problems.append(f"line {index}: record_hash mismatch (record edited?)")
            expected_prev = prev_hash
            if rec.get("prev_record_hash") != expected_prev:
                problems.append(f"line {index}: prev_record_hash mismatch (deleted/inserted line?)")
            prev_hash = rec.get("record_hash")
            index += 1
    return problems
