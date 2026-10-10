"""Metrics (ADR-010 §4): macro-F1, per-family recall, and AUT.

AUT is defined in ADR-010 **before any AUT number exists** (no paper spec
available yet):

- test samples are ordered into consecutive calendar-month windows by
  first-seen timestamp;
- per window, per family: recall if the family is **present** in the window,
  else ``None``;
- window score = macro-average over present families only;
- ``AUT = mean over windows that have a score`` — absent families never
  contribute and never count as zeros; windows never re-weight by size;
- per-family AUT = mean over that family's non-absent windows;
- open-set reporting: a held-out family with zero correct predictions gets
  recall 0.0 at the reporting edge only; AUT still ignores absent windows.

Interim npz-only mode: AUT requires timestamps; the helpers raise a clear
error rather than inventing windows.
"""

from __future__ import annotations

from collections.abc import Iterable

import numpy as np


def confusion(y_true: np.ndarray, y_pred: np.ndarray) -> tuple[int, int, int, int]:
    """(tp, fp, tn, fn) for binary {0,1} labels."""
    y_true = np.asarray(y_true).astype(np.int64)
    y_pred = np.asarray(y_pred).astype(np.int64)
    if y_true.shape != y_pred.shape:
        raise ValueError(f"shape mismatch: {y_true.shape} vs {y_pred.shape}")
    bad = set(np.unique(y_true).tolist()) - {0, 1} | set(np.unique(y_pred).tolist()) - {0, 1}
    if bad:
        raise ValueError(f"labels must be binary {{0,1}}; found {sorted(bad)}")
    tp = int(((y_true == 1) & (y_pred == 1)).sum())
    fp = int(((y_true == 0) & (y_pred == 1)).sum())
    tn = int(((y_true == 0) & (y_pred == 0)).sum())
    fn = int(((y_true == 1) & (y_pred == 0)).sum())
    return tp, fp, tn, fn


def f1_from_counts(tp: int, fp: int, tn: int, fn: int) -> float:
    div = 2 * tp + fp + fn
    return 0.0 if div == 0 else (2 * tp) / div


def macro_f1(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    """Macro-F1 over the classes present in ``y_true`` (both, normally)."""
    tp, fp, tn, fn = confusion(y_true, y_pred)
    positives = tp + fn
    negatives = tn + fp
    f1s = []
    if positives > 0:
        f1s.append(f1_from_counts(tp, fp, 0, fn))
    if negatives > 0:
        f1s.append(f1_from_counts(tn, fn, 0, fp))
    return float(np.mean(f1s)) if f1s else 0.0


def per_group_recall(
    y_true: np.ndarray,
    y_pred: np.ndarray,
    groups: Iterable[str],
    zero_for_absent: bool = False,
) -> dict[str, float | None]:
    """Recall per group (family).

    A group with no positive samples in ``y_true`` scores ``None`` (absent),
    or 0.0 when ``zero_for_absent=True`` (open-set reporting edge — ADR-010:
    zero-at-edge never feeds AUT).
    """
    y_true = np.asarray(y_true).astype(np.int64)
    y_pred = np.asarray(y_pred).astype(np.int64)
    groups = list(groups)
    if len(groups) != len(y_true):
        raise ValueError("groups must align with y_true/y_pred")
    out: dict[str, float | None] = {}
    for g in sorted(set(groups)):
        mask = np.asarray([gi == g for gi in groups])
        yt, yp = y_true[mask], y_pred[mask]
        pos = int((yt == 1).sum())
        if pos == 0:
            out[g] = None if not zero_for_absent else 0.0
            continue
        out[g] = float(((yt == 1) & (yp == 1)).sum()) / pos
    return out


def _month_key(timestamp: int) -> str:
    """Calendar-month bucket of a unix-epoch timestamp (UTC)."""
    import datetime as dt

    return dt.datetime.fromtimestamp(int(timestamp), tz=dt.UTC).strftime("%Y-%m")


def aut(
    y_true: np.ndarray,
    y_pred: np.ndarray,
    families: Iterable[str],
    timestamps: Iterable[int],
) -> tuple[float | None, dict[str, float | None]]:
    """AUT and per-family AUT (ADR-010 §4). Requires timestamps.

    Returns ``(aut_value, per_family_aut)``. ``None`` when no window has a
    score (degenerate input). Raises ``ValueError`` when timestamps or
    families are missing — interim npz-only callers must not call this.
    """
    fams = list(families)
    ts = [int(t) for t in timestamps]
    if not fams or not ts:
        raise ValueError("AUT requires families and timestamps (none given)")
    if not (len(fams) == len(ts) == len(y_true)):
        raise ValueError("y_true, families and timestamps must align")

    fm, yv, pv = (list(fams), np.asarray(y_true), np.asarray(y_pred))
    windows = sorted({_month_key(t) for t in ts})
    all_fams = sorted(set(fm))

    window_scores: list[float] = []
    per_fam_series: dict[str, list[float]] = {f: [] for f in all_fams}
    keys = np.asarray([_month_key(t) for t in ts])
    for w in windows:
        mask = keys == w
        if not mask.any():
            continue
        recalls = per_group_recall(yv[mask], pv[mask], [fm[i] for i in np.flatnonzero(mask)])
        present = [r for g, r in recalls.items() if r is not None]
        if present:
            window_scores.append(float(np.mean(present)))
        for f in all_fams:
            r = recalls.get(f)
            if r is not None:
                per_fam_series[f].append(r)

    aut_value = float(np.mean(window_scores)) if window_scores else None
    per_fam_aut = {
        f: (float(np.mean(s)) if s else None) for f, s in per_fam_series.items()
    }
    return aut_value, per_fam_aut
