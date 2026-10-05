"""Deterministic execution wiring (ADR-009; P0 scope).

Training loops land in P1 through ``bytelens.models``. Until then, this module
owns the one thing every later stage must reproduce: a **deterministic,
seed-bound** computation with recorded determinism flags, executed under the
recorded config and seed (acceptance test 10: same seed ⇒ identical metrics).

The reference pipeline is deliberately tiny — seeded NumPy draws summarised
into metrics — so ``logger.repro`` can prove seed-reproducibility end to end
today, and P1 replaces only the compute step, not the record/lock/repro
machinery.
"""

from __future__ import annotations

from typing import Any

import numpy as np
from logger.hashing import hash_array

DETERMINISM_FLAGS = {
    "algorithms": "deterministic",
    "parallelism": "single-threaded-numpy",
}


def set_all_seeds(seed: int) -> dict[str, int]:
    """Seed every generator a run uses; return the seed map for the record."""
    import random

    random.seed(seed)
    np.random.seed(seed)
    try:
        import torch

        torch.manual_seed(seed)
        framework = int(seed)
    except ImportError:
        framework = int(seed)
    return {"python": int(seed), "numpy": int(seed), "framework": framework}


def resolve_pipeline_config(cfg: dict[str, Any]) -> dict[str, Any]:
    """Fill pipeline defaults for keys absent from the config.

    Defaults are explicit and versioned; a value present in the config always
    wins. The *resolved* config is what gets hashed into the run record.
    """
    defaults = {
        "n_samples": 256,
        "n_features": 8,
        "distribution": "normal",
    }
    resolved = {**defaults, **{k: v for k, v in cfg.items() if v is not None}}
    if int(resolved["n_samples"]) <= 0 or int(resolved["n_features"]) <= 0:
        raise ValueError("n_samples and n_features must be positive")
    if resolved["distribution"] not in ("normal", "uniform"):
        raise ValueError("distribution must be 'normal' or 'uniform'")
    return resolved


def run_pipeline(cfg: dict[str, Any], seed: int) -> tuple[dict[str, float], dict[str, Any]]:
    """Execute the reference pipeline; return ``(metrics, details)``.

    Fully determined by the resolved config + seed: same inputs → bitwise
    identical metrics and the same data hash.
    """
    resolved = resolve_pipeline_config(cfg)
    n = int(resolved["n_samples"])
    d = int(resolved["n_features"])
    set_all_seeds(seed)
    if resolved["distribution"] == "normal":
        x = np.random.default_rng(seed).standard_normal((n, d))
    else:
        x = np.random.default_rng(seed).uniform(-1.0, 1.0, (n, d))
    metrics = {
        "mean": float(x.mean()),
        "std": float(x.std()),
        "first_element": float(x[0, 0]),
    }
    details = {
        "data_hash": hash_array(x),
        "determinism": dict(DETERMINISM_FLAGS),
    }
    return metrics, details
