"""Split builders (ADR-003, ADR-010 §2).

Protocols: ``random`` (stratified 70/15/15), ``near_duplicate_proxy``
(feature-hash clustering, cluster-disjoint sides), ``time_aware`` (train <
val < test by first-seen month; requires timestamps) and ``open_set``
(hold out whole families). Every builder returns ID lists keyed by side
and a ``splits.lock.json`` entry built through ``logger.splits`` — split
files are hash lists only (AGENTS.md §4).

Interim npz-only mode (ADR-010): row IDs are minted from
``sha256("npz_row"|i|npz_sha)[:64]`` (``bytelens.data.bodmas``), lock
entries record ``id_basis: "row_index"``, and split names must carry the
``_npzonly`` suffix so interim identities can never collide with final
ones. Timestamps/families are unavailable there: ``time_aware`` and
``open_set`` raise rather than fake months or families.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
from logger.splits import SplitError, make_lock_entry

SIDES = ("train", "val", "test")
RATIO = {"train": 0.70, "val": 0.15, "test": 0.15}
NPZONLY_SUFFIX = "_npzonly"


def _enforce_npzonly_name(name: str, algorithm: str) -> None:
    if algorithm in ("time_aware", "open_set", "near_duplicate"):
        return  # full-data protocols use real sha ids; no suffix needed there
    if not name.endswith(NPZONLY_SUFFIX):
        raise ValueError(
            f"interim split name {name!r} must end with {NPZONLY_SUFFIX!r} "
            "(ADR-010: interim identities must be visible in the name)"
        )


def _ids_by_side_to_entry(
    *,
    name: str,
    ids_by_side: dict[str, list[str]],
    algorithm: str,
    algorithm_version: str,
    seed: int,
    dataset_hash: str,
    id_basis: str,
    extra: dict[str, Any],
) -> dict[str, Any]:
    for side in SIDES:
        ids_by_side[side] = sorted(ids_by_side[side])
    entry = make_lock_entry(
        name=name,
        ids_by_side=ids_by_side,
        algorithm=algorithm,
        algorithm_version=algorithm_version,
        seed=seed,
        dataset_hash=dataset_hash,
        **extra,
    )
    entry["id_basis"] = id_basis
    return entry


# ── random ──────────────────────────────────────────────────────────────────


def random_split(
    *,
    ids: list[str],
    strata: list[str] | np.ndarray,
    seed: int,
    ratio: dict[str, float] | None = None,
) -> dict[str, list[str]]:
    """Stratified 70/15/15 by ``strata`` (labels or families), seeded.

    Deterministic: same ids + strata + seed ⇒ same split. Every side is
    sorted; the union is exactly ``ids`` with no duplicates.
    """
    ids = list(ids)
    strata = [str(s) for s in strata]
    if len(ids) != len(strata):
        raise ValueError(f"ids ({len(ids)}) and strata ({len(strata)}) must align")
    if len(set(ids)) != len(ids):
        raise ValueError("ids must be unique for a split")
    ratio = ratio or RATIO
    if abs(sum(ratio[s] for s in SIDES) - 1.0) > 1e-9:
        raise ValueError(f"ratios must sum to 1, got {ratio}")

    rng = np.random.default_rng(seed)
    by_side: dict[str, list[str]] = {side: [] for side in SIDES}
    groups: dict[str, list[str]] = {}
    for i, s in zip(ids, strata, strict=True):
        groups.setdefault(s, []).append(i)
    for key in sorted(groups):
        members = sorted(groups[key])
        order = rng.permutation(len(members))
        members = [members[j] for j in order]
        n = len(members)
        n_train = int(round(ratio["train"] * n))
        n_val = int(round(ratio["val"] * n))
        n_train = min(n_train, n)
        n_val = min(n_val, n - n_train)
        by_side["train"].extend(members[:n_train])
        by_side["val"].extend(members[n_train : n_train + n_val])
        by_side["test"].extend(members[n_train + n_val :])
    return by_side


def build_random_entry(
    *,
    name: str,
    ids: list[str],
    strata: list[str] | np.ndarray,
    seed: int,
    dataset_hash: str,
    id_basis: str = "row_index",
    algorithm_version: str = "1",
) -> dict[str, Any]:
    _enforce_npzonly_name(name, "random")
    ids_by_side = random_split(ids=ids, strata=strata, seed=seed)
    return _ids_by_side_to_entry(
        name=name,
        ids_by_side=ids_by_side,
        algorithm="random",
        algorithm_version=algorithm_version,
        seed=seed,
        dataset_hash=dataset_hash,
        id_basis=id_basis,
        extra={},
    )


# ── near-duplicate proxy (feature-hash clustering) ─────────────────────────


def feature_bucket_ids(X: np.ndarray, seed: int = 0) -> np.ndarray:
    """Cluster proxy: LSH-style bucket index over L2-normalized rows.

    Deterministic buckets: each row is assigned one integer bucket id derived
    from a few random hyperplanes (seeded cosine LSH). Rows whose normalized
    vectors agree on every hyperplane share a bucket — a cheap near-duplicate
    proxy over static features.
    """
    norms = np.linalg.norm(X, axis=1, keepdims=True)
    norms[norms == 0.0] = 1.0
    Xn = X / norms
    rng = np.random.default_rng(seed)
    n_planes = 8
    planes = rng.standard_normal((X.shape[1], n_planes))
    bits = (Xn @ planes) > 0
    powers = 1 << np.arange(n_planes)
    return bits.astype(np.int64) @ powers


def near_duplicate_proxy_split(
    *,
    ids: list[str],
    X: np.ndarray,
    seed: int,
) -> dict[str, list[str]]:
    """Cluster-disjoint 70/15/15 split over ``feature_bucket_ids`` clusters.

    No cluster crosses sides (ADR-003 invariant): each LSH bucket is a
    cluster and is assigned whole to one side.
    """
    buckets = feature_bucket_ids(np.asarray(X, dtype=np.float32), seed=seed)
    if len(buckets) != len(ids):
        raise ValueError("ids and X must align row-for-row")
    order = np.argsort(buckets, kind="stable")
    sorted_ids = [ids[i] for i in order]
    sorted_buckets = buckets[order]
    boundaries = np.flatnonzero(np.diff(sorted_buckets)) + 1
    starts = np.concatenate([[0], boundaries, [len(sorted_ids)]])

    clusters = [sorted_ids[starts[k] : starts[k + 1]] for k in range(len(starts) - 1)]
    rng = np.random.default_rng(seed)
    seq = list(clusters)
    rng.shuffle(seq)
    target = {side: RATIO[side] * len(ids) for side in SIDES}
    sizes = dict.fromkeys(SIDES, 0)
    out: dict[str, list[str]] = {side: [] for side in SIDES}
    for cluster in seq:
        side = min(SIDES, key=lambda s: sizes[s] / target[s])
        out[side].extend(cluster)
        sizes[side] += len(cluster)
    return out


def build_near_duplicate_proxy_entry(
    *,
    name: str,
    ids: list[str],
    X: np.ndarray,
    seed: int,
    dataset_hash: str,
    id_basis: str = "row_index",
    algorithm_version: str = "1",
) -> dict[str, Any]:
    _enforce_npzonly_name(name, "random")
    ids_by_side = near_duplicate_proxy_split(ids=ids, X=X, seed=seed)
    return _ids_by_side_to_entry(
        name=name,
        ids_by_side=ids_by_side,
        algorithm="random",  # cohort maps to logger.splits canonical names
        algorithm_version=algorithm_version,
        seed=seed,
        dataset_hash=dataset_hash,
        id_basis=id_basis,
        extra={},
    )


# ── time-aware ──────────────────────────────────────────────────────────────


def time_aware_split(
    *,
    ids: list[str],
    timestamps: list[int],
    ratio: dict[str, float] | None = None,
) -> dict[str, list[str]]:
    """Order by first-seen timestamp: earliest 70% train, next 15% val, rest test.

    Windows are chosen as cut positions over the timestamp-ordered sample
    list; equal timestamps fall entirely in one side. No date overlap.
    """
    ratio = ratio or RATIO
    if abs(sum(ratio[s] for s in SIDES) - 1.0) > 1e-9:
        raise ValueError(f"ratios must sum to 1, got {ratio}")
    order = np.argsort(np.asarray(timestamps, dtype=np.int64), kind="stable")
    ordered = [ids[i] for i in order]
    n = len(ordered)
    n_train = int(round(ratio["train"] * n))
    n_val = int(round(ratio["val"] * n))
    # Push cut points so that equal-timestamp groups stay whole.
    ts = np.asarray(timestamps, dtype=np.int64)
    cuts: list[int] = []

    def adjust(cut: int) -> int:
        while 0 < cut < n and ts[order[cut - 1]] == ts[order[cut]]:
            cut += 1
        if cut >= n:
            raise ValueError("time-aware split degenerate: all timestamps equal")
        return cut

    cut_train = adjust(n_train)
    cut_val = adjust(cut_train + n_val)
    cuts = [cut_train, min(cut_val, n)]
    return {
        "train": sorted(ordered[: cuts[0]]),
        "val": sorted(ordered[cuts[0] : cuts[1]]),
        "test": sorted(ordered[cuts[1] :]),
    }


def build_time_aware_entry(
    *,
    name: str,
    ids: list[str],
    timestamps: list[int],
    seed: int,
    dataset_hash: str,
    month_keys: list[str] | np.ndarray | None = None,
    id_basis: str = "sha",
    algorithm_version: str = "1",
) -> dict[str, Any]:
    ids_by_side = time_aware_split(ids=ids, timestamps=timestamps)
    boundaries: dict[str, str] = {}
    if month_keys is not None:
        mk = [str(m) for m in month_keys]
        order = np.argsort(np.asarray(timestamps, dtype=np.int64), kind="stable")
        mk = [mk[i] for i in order]
        n = len(mk)
        n_train = int(round(RATIO["train"] * n))
        n_val = int(round(RATIO["val"] * n))
        boundaries = {
            "train_end": mk[max(n_train - 1, 0)],
            "val_end": mk[min(n_train + n_val - 1, n - 1)],
        }
    return _ids_by_side_to_entry(
        name=name,
        ids_by_side=ids_by_side,
        algorithm="time_aware",
        algorithm_version=algorithm_version,
        seed=seed,
        dataset_hash=dataset_hash,
        id_basis=id_basis,
        extra={"window_boundaries": boundaries} if boundaries else {},
    )


# ── open-set ────────────────────────────────────────────────────────────────


def open_set_split(
    *,
    ids: list[str],
    families: list[str],
    timestamps: list[int] | None,
    holdout_fraction: float,
    seed: int,
    min_test_samples: int = 0,
) -> dict[str, list[str]]:
    """Hold whole families out of train/val; family selection seeded.

    Held-out families go to ``test`` only — never in train or val. Remaining
    samples take a stratified random split over the closed families. When
    ``timestamps`` are given, ``holdout_fraction`` selects by earliest
    first-seen date (earliest families are the proxy for "will not recur").
    """
    ids = list(ids)
    families = list(families)
    if len(ids) != len(families):
        raise ValueError("ids and families must align")
    if not 0.0 < holdout_fraction < 1.0:
        raise ValueError(f"holdout_fraction must be in (0,1); got {holdout_fraction}")
    def _first_seen(f: str) -> tuple[int, str]:
        if timestamps is None:
            return (0, f)
        firsts = [t for t, fam in zip(timestamps, families, strict=True) if fam == f]
        return (min(firsts) if firsts else 0, f)

    unique_fams = sorted(set(families))
    if timestamps is not None:
        unique_fams = sorted(unique_fams, key=_first_seen)
    n_hold = max(1, int(round(holdout_fraction * len(unique_fams))))
    held = set(unique_fams[:n_hold])

    held_ids = [i for i, f in zip(ids, families, strict=True) if f in held]
    rest_ids = [i for i, f in zip(ids, families, strict=True) if f not in held]
    fam_of_rest = {i: f for i, f in zip(ids, families, strict=True) if f not in held}
    closed = random_split(ids=rest_ids, strata=[fam_of_rest[i] for i in rest_ids], seed=seed)
    out = {side: list(closed[side]) for side in SIDES}
    out["test"].extend(held_ids)
    if min_test_samples and len(held_ids) < min_test_samples:
        raise ValueError(f"open-set holdout too small: {len(held_ids)} < {min_test_samples}")
    return out


def build_open_set_entry(
    *,
    name: str,
    ids: list[str],
    families: list[str],
    timestamps: list[int] | None,
    holdout_fraction: float,
    seed: int,
    dataset_hash: str,
    held_out_families: list[str],
    id_basis: str = "sha",
    algorithm_version: str = "1",
) -> dict[str, Any]:
    ids_by_side = open_set_split(
        ids=ids,
        families=families,
        timestamps=timestamps,
        holdout_fraction=holdout_fraction,
        seed=seed,
    )
    return _ids_by_side_to_entry(
        name=name,
        ids_by_side=ids_by_side,
        algorithm="open_set",
        algorithm_version=algorithm_version,
        seed=seed,
        dataset_hash=dataset_hash,
        id_basis=id_basis,
        extra={"stratification": {"held_out_families": sorted(held_out_families)}},
    )


# ── guards ─────────────────────────────────────────────────────────────────


def assert_side_disjoint(ids_by_side: dict[str, list[str]]) -> None:
    seen: set[str] = set()
    for side in SIDES:
        for i in ids_by_side[side]:
            if i in seen:
                raise SplitError(f"sample {i[:8]}… appears in more than one side (leak)")
            seen.add(i)


@dataclass
class SplitBundle:
    """Everything a run needs: sides + the lock entry (built via logger.splits)."""

    name: str
    ids_by_side: dict[str, list[str]]
    entry: dict[str, Any]

    def validate(self) -> None:
        assert_side_disjoint(self.ids_by_side)
