"""Metrics (ADR-010 §4, rev 2): macro-F1, per-family recall, and AUT.

AUT follows the **paper's definition**, pre-registered in ADR-010 §4 rev 2
*before any AUT number exists*:

- windows are consecutive calendar months ordered by first-seen timestamp;
- a family is **eligible** for (family, window) iff it has training samples
  AND ≥1 sample in the window (``train_families`` argument — families
  absent from train are the open-set axis and never enter AUT);
- window score = **macro-F1** over the eligible families' samples in the
  window (``macro_f1`` below, not per-family recall);
- **AUT(f) = trapezoidal integral of f's window scores over window index,
  normalized by span** — trapezoid rule over consecutive windows with
  scores; equals the plain mean when all windows score;
- headline AUT = unweighted mean over eligible families' AUTs;
- degenerate inputs (no timestamps/families, no eligible points) raise or
  return ``None`` per-function contract — never silently zero.

Drift guard: ``tests/unit/test_metrics.py`` pins hand-computed trapezoid
values; a formula change fails the tests.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence

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


def _trapezoid(x: Sequence[float], y: Sequence[float]) -> float:
    """Trapezoidal integral of y over x; normalized by the x-span.

    Degenerate span (single point) returns y[0] — one window is still one
    score, not zero.
    """
    if len(x) != len(y) or len(x) == 0:
        raise ValueError("trapezoid needs non-empty aligned x/y")
    if len(x) == 1:
        return float(y[0])
    area = 0.0
    span = 0.0
    for i in range(1, len(x)):
        dx = float(x[i]) - float(x[i - 1])
        area += 0.5 * (float(y[i]) + float(y[i - 1])) * dx
        span += dx
    return area / span if span > 0 else float(y[0])


def aut(
    y_true: np.ndarray,
    y_pred: np.ndarray,
    families: Iterable[str],
    timestamps: Iterable[int],
    *,
    train_families: Iterable[str] | None = None,
) -> tuple[float | None, dict[str, float | None]]:
    """AUT and per-family AUT — ADR-010 §4 rev 2 (paper definition).

    Trapezoid over windows of macro-F1; a family is eligible for a window
    iff it has ≥1 sample in that window **and** (when ``train_families`` is
    given) is present in training. Families absent from train are the
    open-set axis: excluded from AUT by construction, never averaged there.

    Returns ``(headline_aut, per_family_aut)``. ``headline_aut`` is the
    unweighted mean of eligible families' AUTs, or ``None`` when no family
    yields a series. Raises ``ValueError`` on missing/unaligned inputs.
    """
    fams = [str(f) for f in families]
    ts = [int(t) for t in timestamps]
    if not fams or not ts:
        raise ValueError("AUT requires families and timestamps (none given)")
    if not (len(fams) == len(ts) == len(y_true)):
        raise ValueError("y_true, families and timestamps must align")

    trained = {str(f) for f in train_families} if train_families is not None else set(fams)
    if not trained:
        raise ValueError("train_families given but empty — every family would be ineligible")

    yv = np.asarray(y_true)
    pv = np.asarray(y_pred)
    keys = [_month_key(t) for t in ts]
    windows = sorted(set(keys))
    win_idx = {w: i for i, w in enumerate(windows)}

    per_fam_x: dict[str, list[int]] = {}
    per_fam_y: dict[str, list[float]] = {}
    for w in windows:
        mask = np.asarray([k == w for k in keys])
        w_fams = [fams[i] for i in np.flatnonzero(mask)]
        eligible = sorted(set(w_fams) & trained)
        if not eligible:
            continue
        keep = np.asarray([f in eligible for f in w_fams])
        idx = np.flatnonzero(mask)[keep]
        score = macro_f1(yv[idx], pv[idx])
        for f in eligible:
            i = win_idx[w]
            per_fam_x.setdefault(f, []).append(i)
            per_fam_y.setdefault(f, []).append(score)

    per_fam_aut = {
        f: _trapezoid(x, s) if x else None
        for f, (x, s) in (
            (f, (per_fam_x.get(f, []), per_fam_y.get(f, []))) for f in sorted(per_fam_x)
        )
    }
    scored = [v for v in per_fam_aut.values() if v is not None]
    headline = float(np.mean(scored)) if scored else None
    return headline, per_fam_aut
