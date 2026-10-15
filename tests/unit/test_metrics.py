"""Unit tests for bytelens.eval.metrics (ADR-010 §4 rev 2).

Hand-computed expectations on tiny synthetic cases; no sklearn dependency.
The AUT tests are **drift guards**: they pin the paper's trapezoid-over-
windows macro-F1 formula with exact hand-computed values, so any
reintroduction of plain-mean or recall-based scoring fails here.
"""

from __future__ import annotations

import numpy as np
import pytest
from bytelens.eval.metrics import (
    _trapezoid,
    aut,
    confusion,
    f1_from_counts,
    macro_f1,
    per_group_recall,
)


class TestConfusion:
    def test_counts(self) -> None:
        y = np.array([0, 1, 1, 0, 1])
        p = np.array([0, 1, 0, 0, 1])
        assert confusion(y, p) == (2, 0, 2, 1)

    def test_f1_pair(self) -> None:
        assert f1_from_counts(2, 0, 2, 1) == pytest.approx(4 / 5)


class TestMacroF1:
    def test_perfect(self) -> None:
        y = np.array([0, 1, 1, 0])
        assert macro_f1(y, y) == 1.0

    def test_hand_computed(self) -> None:
        # tp=2, fn=1, tn=2, fp=0 ⇒ F1×2 = 2·2/(2·2+0+1) = 4/5 for both classes.
        y = np.array([0, 1, 1, 0, 1])
        p = np.array([0, 1, 0, 0, 1])
        assert macro_f1(y, p) == pytest.approx(4 / 5)

    def test_all_wrong(self) -> None:
        y = np.array([0, 1])
        p = np.array([1, 0])
        assert macro_f1(y, p) == 0.0


class TestPerGroupRecall:
    def test_basic_and_absent(self) -> None:
        y_true = np.array([1, 1, 0, 0])
        y_pred = np.array([1, 0, 1, 1])
        groups = ["a", "a", "b", "b"]  # b has no positives ⇒ absent
        r = per_group_recall(y_true, y_pred, groups)
        assert r["a"] == pytest.approx(1 / 2)
        assert r["b"] is None
        r0 = per_group_recall(y_true, y_pred, groups, zero_for_absent=True)
        assert r0["b"] == 0.0


class TestTrapezoid:
    """Pins the integrator itself (drift guard, ADR-010 rev 2)."""

    def test_uniform_windows_equal_segment_mean(self) -> None:
        # Uniform spacing trapezoid, computed by hand:
        # y=[0.5,1,0,1] over x=[0..3] = (0.75+0.5+0.5)/3 = 0.5833…
        # (NOT the plain mean 0.625 — the trapezoid underweights the V middle;
        # that distinction is the whole point of the drift guard.)
        assert _trapezoid([0, 1, 2, 3], [0.5, 1.0, 0.0, 1.0]) == pytest.approx(7 / 12)

    def test_constant_series_is_constant(self) -> None:
        assert _trapezoid([0, 1, 2], [0.8, 0.8, 0.8]) == pytest.approx(0.8)

    def test_nonuniform_weights_by_span(self) -> None:
        # x=[0,1,3], y=[0,1,0]: segments ½(0+1)·1 + ½(1+0)·2 = 1.5; span 3 ⇒ 0.5.
        assert _trapezoid([0, 1, 3], [0.0, 1.0, 0.0]) == pytest.approx(0.5)
        # A plain mean would give (0+1+0)/3 = ⅓ — different, and that is the point.

    def test_single_point_is_itself(self) -> None:
        assert _trapezoid([0], [0.7]) == pytest.approx(0.7)

class TestAUT:
    """Paper-definition drift guards (ADR-010 §4 rev 2)."""

    def _eligible_series(self, train_fams: set[str]) -> tuple[list, tuple]:
        """Two calendar-month windows (Sept, Oct 2020); family ``a`` trained
        and present in both; family ``c`` never in training (open-set axis
        — must be excluded from AUT entirely)."""
        y_true = np.array([1, 1, 0, 1, 1, 0, 1, 1, 0])
        y_pred = np.array([1, 0, 0, 1, 0, 0, 0, 0, 0])
        fams = ["a", "a", "a", "a", "a", "a", "c", "c", "c"]
        # a: Sept ×5, Oct ×1;  c: Sept ×2, Oct ×1 (never in train)
        ts = (
            [1_599_900_000] * 5  # Sept 2020
            + [1_602_200_000]  # Oct 2020
            + [1_599_900_000, 1_599_900_000, 1_602_200_000]
        )
        return (y_true, y_pred, fams, ts), train_fams

    def test_macro_f1_window_scores(self) -> None:
        (y, p, fams, ts), train_a = self._eligible_series({"a"})
        # Sept: a's rows 0–4 all eligible (c's rows 6–7 never trained ⇒
        # excluded). a-only macro-F1: y=[1,1,0,1,1] p=[1,0,0,1,0]
        # ⇒ tp=2, fn=2, tn=1, fp=0 ⇒ F1a=2/3, F1b=1/2 ⇒ macro 7/12.
        f1_sept = macro_f1(y[[0, 1, 2, 3, 4]], p[[0, 1, 2, 3, 4]])
        # Oct: a row 5, y=[0] p=[0] ⇒ single negative, correct ⇒ macro 1.0.
        f1_oct = macro_f1(y[[5]], p[[5]])
        assert f1_sept == pytest.approx(7 / 12)
        assert f1_oct == pytest.approx(1.0)
        total, per_fam = aut(y, p, fams, ts, train_families=train_a)
        # Family a series x=[0,1], y=[7/12, 1.0] → trapezoid = 19/24 (hand).
        # Headline = family a only (c excluded, never trained).
        assert total == pytest.approx(19 / 24)
        assert per_fam["a"] == pytest.approx(19 / 24)
        assert "c" not in per_fam  # never trained ⇒ open-set axis, excluded

    def test_nonuniform_window_parallel_spans(self) -> None:
        """A family sampled in month 0 then month 2 (gap at month 1): the
        month-1 span is weighted by its width — the trapezoid's point."""
        y_true = np.array([1, 1, 1, 1])
        y_pred = np.array([1, 0, 1, 1])
        fams = ["a", "a", "a", "a"]
        ts = [1_600_000_000, 1_600_000_000, 1_602_000_000, 1_602_000_000]  # months 0 and 2
        w0 = macro_f1(y_true[:2], y_pred[:2])  # tp=1, fn=1
        w2 = macro_f1(y_true[2:], y_pred[2:])  # perfect
        total, per_fam = aut(y_true, y_pred, fams, ts)
        # Trapezoid over x=[0,2], y=[w0,w2] = ½(w0+w2)·2 / 2 = mean of the two.
        expected = _trapezoid([0, 2], [w0, w2])
        assert total == pytest.approx(expected)
        assert per_fam["a"] == pytest.approx(expected)


class TestAUTDegenerate:
    def test_missing_timestamps_raise(self) -> None:
        y = np.array([1, 0])
        with pytest.raises(ValueError):
            aut(y, y, ["a", "b"], [])
        with pytest.raises(ValueError):
            aut(y, y, [], [1, 2])

    def test_family_absent_from_train_excluded(self) -> None:
        y = np.array([1, 1])
        with pytest.raises(ValueError):
            aut(y, y, ["a", "b"], [1, 2], train_families=[])
