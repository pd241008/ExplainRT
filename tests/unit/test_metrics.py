"""Unit tests for bytelens.eval.metrics (ADR-010 §4).

Hand-computed expectations on tiny synthetic cases; no sklearn dependency.
"""

from __future__ import annotations

import numpy as np
import pytest
from bytelens.eval.metrics import aut, confusion, f1_from_counts, macro_f1, per_group_recall


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


class TestAUT:
    def _data(self) -> tuple[np.ndarray, np.ndarray, list[str], list[int]]:
        # Two families across two months.
        y_true = np.array([1, 1, 0, 1, 1, 0])
        y_pred = np.array([1, 0, 0, 1, 1, 0])
        fams = ["a", "a", "a", "b", "b", "b"]
        # a: month 1 ×2, month 2 ×1; b: month 2 ×3
        ts = (
            [1_600_000_000, 1_600_000_000, 1_602_000_000]
            + [1_602_000_000, 1_602_000_000, 1_602_000_000]
        )
        return y_true, y_pred, fams, ts

    def test_aut_ignores_absent_family_month(self) -> None:
        y_true, y_pred, fams, ts = self._data()
        total, _ = aut(y_true, y_pred, fams, ts)
        # Month 1: family a present with recall 1/2 ⇒ window score 0.5.
        # Month 2: a's row is benign (absent); b recall 2/2 ⇒ window score 1.0.
        assert total == pytest.approx((0.5 + 1.0) / 2)

    def test_per_family_aut_skips_absent(self) -> None:
        y_true, y_pred, fams, ts = self._data()
        _, per_fam = aut(y_true, y_pred, fams, ts)
        # Family a: month1 = 0.5 (month-2 row is benign ⇒ absent) ⇒ mean 0.5.
        assert per_fam["a"] == pytest.approx(0.5)
        # Family b: only month 2 = 1.0 (month 1 absent ⇒ skipped).
        assert per_fam["b"] == pytest.approx(1.0)

    def test_missing_timestamps_raise(self) -> None:
        y = np.array([1, 0])
        with pytest.raises(ValueError):
            aut(y, y, ["a", "b"], [])
        with pytest.raises(ValueError):
            aut(y, y, [], [1, 2])
