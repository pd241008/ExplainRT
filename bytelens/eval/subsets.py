"""10% pilot subset builder (ADR-010 §3; ADR-009 subsets discipline).

Samples 10% of the data **within each stratum** (final mode: month × family;
interim npz-only mode: label × feature-hash bucket) with a fixed seed from
the config. Strata smaller than a minimum size contribute proportionally and
are recorded — nothing is silently dropped. The output is a frozen ID list:
no resampling at run time (logger.splits docstring).

The subset's lock entry records ``sampling_fraction`` and the
``stratification`` spec, and pilot runs carry the ``pilot-10pct`` tag so
``paper/tables.py`` refuses them.
"""

from __future__ import annotations

from typing import Any

import numpy as np
from logger.splits import make_lock_entry

from bytelens.eval.splits import feature_bucket_ids

SAMPLING_FRACTION = 0.10
MIN_STRATUM = 50  # ADR-010 pre-registration: fixed before any pilot split


def stratified_subset(
    *,
    ids: list[str],
    strata: list[str],
    fraction: float = SAMPLING_FRACTION,
    seed: int,
    min_stratum: int = MIN_STRATUM,
) -> tuple[list[str], dict[str, int]]:
    """Pick ``round(fraction × |stratum|)`` ids per stratum (≥ min contribution).

    A stratum smaller than ``min_stratum`` keeps at least one sample when
    non-empty (rounded-up fraction), so tiny families still appear. Returns
    the selected ids and the per-stratum counts actually sampled.
    """
    if len(ids) != len(strata):
        raise ValueError("ids and strata must align")
    if not 0.0 < fraction <= 1.0:
        raise ValueError(f"fraction must be in (0,1]; got {fraction}")
    rng = np.random.default_rng(seed)
    groups: dict[str, list[str]] = {}
    for i, s in zip(ids, strata, strict=True):
        groups.setdefault(s, []).append(i)
    chosen: list[str] = []
    counts: dict[str, int] = {}
    for key in sorted(groups):
        members = sorted(groups[key])
        n_take = max(1, int(round(fraction * len(members)))) if len(members) < min_stratum else int(
            round(fraction * len(members))
        )
        n_take = min(n_take, len(members))
        order = rng.permutation(len(members))[:n_take]
        picked = [members[j] for j in sorted(order)]
        chosen.extend(picked)
        counts[key] = len(picked)
    return sorted(chosen), counts


def subset_strata_npzonly(y: np.ndarray, X: np.ndarray, seed: int) -> list[str]:
    """Interim strata: label × feature-hash bucket (no month/family yet)."""
    buckets = feature_bucket_ids(np.asarray(X), seed=seed)
    return [f"{int(lbl)}_{int(b)}" for lbl, b in zip(y, buckets, strict=True)]


def build_subset_entry(
    *,
    name: str,
    ids: list[str],
    strata: list[str],
    seed: int,
    dataset_hash: str,
    base_split_hash: str | None = None,
    fraction: float = SAMPLING_FRACTION,
    min_stratum: int = MIN_STRATUM,
    id_basis: str = "row_index",
) -> dict[str, Any]:
    """One ``splits.lock.json`` entry for the pilot subset.

    The subset is a single-side ``test``-shaped ID list recorded through a
    lock entry with ``sampling_fraction`` + ``stratification`` metadata.
    ``base_split_hash`` ties the subset to the split it was drawn from.
    """
    selected, counts = stratified_subset(
        ids=sorted(ids), strata=strata, fraction=fraction, seed=seed,
        min_stratum=min_stratum,
    )
    ids_by_side = {"train": [], "val": [], "test": sorted(selected)}
    entry = make_lock_entry(
        name=name,
        ids_by_side=ids_by_side,
        algorithm="random",
        algorithm_version="1",
        seed=seed,
        dataset_hash=dataset_hash,
        sampling_fraction=fraction,
        stratification={
            "by": ["month", "family"] if id_basis == "sha" else ["label", "feature_bucket"],
            "min_stratum": min_stratum,
            "sampled_counts": counts,
        },
    )
    entry["id_basis"] = id_basis
    if base_split_hash is not None:
        entry["base_split_hash"] = base_split_hash
    return entry
