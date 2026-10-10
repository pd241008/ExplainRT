"""LightGBM baseline (ADR-010 §5) — the first real model in ByteLens.

Config-driven only: every hyperparameter, the seed, and the split name come
from the resolved experiment YAML; nothing defaults in code (hard rule,
AGENTS.md §2). Determinism flags are set for the record. The training entry
point is pure — it takes arrays and returns predictions + an artifact digest —
so a runner (``runner.experiment`` / a Track A script) wires it to the
RunRecorder; that keeps records, locks, and training concerns separate.

Determinism: LightGBM's histogram method is multi-threaded but seeded via
``seed``/``feature_fraction_seed`` etc. Records carry the seeds map and the
determinism flags so a rerun is checkable via ``logger.repro``.
"""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

import numpy as np
from runner.execution import set_all_seeds

MODEL_NAME = "lightgbm"

DEFAULT_PARAMS: dict[str, Any] = {
    "objective": "binary",
    "verbosity": -1,
}


def resolve_params(cfg_params: dict[str, Any] | None) -> dict[str, Any]:
    """Model params = defaults + config overrides (config always wins)."""
    params = {**DEFAULT_PARAMS, **(cfg_params or {})}
    return params


def _determinism_flags(n_threads: int) -> dict[str, Any]:
    return {
        "framework": "lightgbm",
        "num_threads": n_threads,  # recorded: thread count affects float sums
        "force_row_wise": True,
    }


def train_lightgbm(
    X_train: np.ndarray,
    y_train: np.ndarray,
    *,
    seed: int,
    params: dict[str, Any] | None = None,
    num_threads: int = 1,
) -> dict[str, Any]:
    """Fit the baseline; return ``(model, info)`` — pure, no logging here.

    ``info`` carries the resolved params, determinism flags, and the model's
    serialized sha256 (``model_artifact_sha256`` for the run record).
    """
    try:
        import lightgbm as lgb
    except ImportError as exc:  # pragma: no cover - pinned in requirements
        raise RuntimeError("lightgbm is not installed; requirements.txt pins it") from exc

    set_all_seeds(seed)
    resolved = resolve_params(params)
    resolved = {
        **resolved,
        "seed": int(seed),
        "feature_fraction_seed": int(seed),
        "bagging_seed": int(seed),
        "data_random_seed": int(seed),
        "num_threads": int(num_threads),
        "force_row_wise": True,
    }
    booster = lgb.train(
        resolved,
        lgb.Dataset(X_train, label=y_train),
        num_boost_round=int(resolved.get("num_boost_round", 100)),
    )
    blob = booster.model_to_string() if hasattr(booster, "model_to_string") else None
    artifact_sha = hashlib.sha256(blob.encode("utf-8")).hexdigest() if blob else None
    return {
        "booster": booster,
        "resolved_params": resolved,
        "determinism": _determinism_flags(num_threads),
        "model_artifact_sha256": artifact_sha,
    }


def predict(booster: Any, X: np.ndarray, threshold: float = 0.5) -> np.ndarray:
    """Binary predictions from the booster at ``threshold``."""
    proba = booster.predict(np.asarray(X))
    return (proba >= threshold).astype(np.int64)


def save_model(booster: Any, path: str | Path) -> dict[str, Any]:
    """Serialize the booster under versioned names in ``models/``; return digest."""
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(booster.model_to_string().encode("utf-8"))
    from logger.hashing import hash_file

    return {"path": p.as_posix(), "model_artifact_sha256": hash_file(p)}
