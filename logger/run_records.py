"""Structured run records (AGENTS.md section 8; ADR-007).

One record per run. The record is the only path by which a number may reach
the paper, README, or an ADR (hard rule, AGENTS.md section 2).
"""

from __future__ import annotations

import hashlib
import json
import platform
import subprocess
import sys
import time
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

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
    canonical = json.dumps(config, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _git_sha(repo_dir: Path | None) -> str | None:
    """Short git SHA of the working tree, or None outside a git repo."""
    try:
        out = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            capture_output=True,
            text=True,
            check=True,
            cwd=repo_dir,
        )
    except (OSError, subprocess.CalledProcessError):
        return None
    return out.stdout.strip()


def _requirements_hash(repo_dir: Path | None) -> str | None:
    """SHA-256 of requirements.txt, or None when the file is absent."""
    if repo_dir is None:
        return None
    req = repo_dir / "requirements.txt"
    if not req.is_file():
        return None
    return hashlib.sha256(req.read_bytes()).hexdigest()


def capture_env(repo_dir: Path | None = None) -> dict[str, Any]:
    """Capture the execution environment for a run record.

    Never estimates: missing values (git, GPU) are null.
    """
    del repo_dir  # reserved for explicit repo discovery; git lookup uses cwd
    return {
        "python": sys.version.split()[0],
        "platform": platform.platform(),
        "machine": platform.machine(),
        "cpu_count": None if platform.system() == "unknown" else _cpu_count(),
        "gpu": _gpu(),
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


@dataclass
class RunRecord:
    """One experiment run: identity, inputs, metrics, environment."""

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

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), sort_keys=True, separators=(",", ":"))

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> "RunRecord":
        missing = [k for k in REQUIRED_FIELDS if k not in raw]
        if missing:
            raise ValueError(f"run record missing required fields: {missing}")
        return cls(**{k: raw[k] for k in REQUIRED_FIELDS})


class RunRecorder:
    """Creates and persists run records as JSON Lines.

    Usage:
        rec = RunRecorder(output_dir).start(config=cfg, seed=42,
                                            model_name="malconv")
        ... run ...
        RunRecorder.finish(rec, metrics={...}, wall_time_sec=...)
    """

    def __init__(self, output_dir: str | Path = "logger/runs") -> None:
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def start(
        self,
        config: dict[str, Any],
        seed: int,
        model_name: str,
        dataset_split_hash: str | None = None,
    ) -> RunRecord:
        """Open a record at run start. ``metrics`` are filled by ``finish``."""
        now = time.time()
        record = RunRecord(
            run_id=f"{time.strftime('%Y%m%d-%H%M%S', time.gmtime(now))}-{uuid.uuid4().hex[:8]}",
            created=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(now)),
            config_hash=config_hash(config),
            config=config,
            git_sha=_git_sha(None),
            seed=seed,
            dataset_split_hash=dataset_split_hash,
            model_name=model_name,
            hardware=capture_env(),
            requirements_hash=_requirements_hash(Path.cwd()),
        )
        return record

    @staticmethod
    def finish(
        record: RunRecord, metrics: dict[str, float], wall_time_sec: float
    ) -> RunRecord:
        record.metrics = dict(metrics)
        record.wall_time_sec = float(wall_time_sec)
        return record


def append_jsonl(record: RunRecord, path: str | Path) -> Path:
    """Append one record as a JSON line, creating the file if needed."""
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("a", encoding="utf-8") as f:
        f.write(record.to_json() + "\n")
    return p


def read_jsonl(path: str | Path) -> list[RunRecord]:
    """Read all records from a JSONL file. Skips blank lines."""
    records: list[RunRecord] = []
    with Path(path).open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            records.append(RunRecord.from_dict(json.loads(line)))
    return records
