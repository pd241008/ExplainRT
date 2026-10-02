"""Evaluation: splits, AUT, open-set protocol, statistics, audits S1-S7.

Serves RQ1 (evaluation bias: random vs near-duplicate vs time-aware splits),
RQ2 (shortcut audits), and every paper metric. Statistics use cluster
bootstrap and permutation tests (ADR-004).

Invariants (tested in ``tests/unit/test_splits.py`` and
``tests/unit/test_stats.py``, P0-P2):

- no near-duplicate cluster crosses splits;
- time-aware windows: train dates < validation dates < test dates;
- AUT handles absent families (families that appear only in later windows);
- fixed seeds + same inputs give identical results (seeded determinism);
- split files are hash-list-only (no binaries) and tracked in
  ``datasets/splits/``.

Primary scope: audits S1-S4. S5-S7 are supplement.

Implemented across P1-P2. Until then the public functions raise
``NotImplementedError``.
"""

from __future__ import annotations

__all__ = ["build_splits", "area_under_time", "cluster_bootstrap"]


def build_splits(records: object, protocol: str, seed: int) -> object:
    """Build random / near-duplicate / time-aware / open-set splits.

    Deterministic for a fixed seed. Raises ``NotImplementedError`` until P1.
    """
    raise NotImplementedError("build_splits lands with P1 (data + baselines)")


def area_under_time(curve: object) -> float:
    """AUT over a time-ordered performance curve, absent-family aware.

    Raises ``NotImplementedError`` until P2.
    """
    raise NotImplementedError("area_under_time lands with P2 (pilot audits)")


def cluster_bootstrap(samples: object, clusters: object, n_boot: int, seed: int) -> object:
    """Cluster bootstrap for headline CIs (ADR-004). Raises until P2."""
    raise NotImplementedError("cluster_bootstrap lands with P2 (stats protocol)")
