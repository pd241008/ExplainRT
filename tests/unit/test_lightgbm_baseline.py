"""Unit tests for bytelens.models.lightgbm_baseline (ADR-010 §5 + §6).

Track A sanity tests (synthetic data only, AGENTS.md §7):

1. shuffled labels ⇒ macro-F1 near chance;
2. on synthetic drift data, random-split macro-F1 > time-aware macro-F1
   (the RQ1 gap reproduced on data we control).
"""

from __future__ import annotations

import numpy as np
import pytest
from bytelens.eval.metrics import macro_f1
from bytelens.eval.splits import random_split, time_aware_split
from bytelens.models.lightgbm_baseline import MODEL_NAME, predict, train_lightgbm

pytest.importorskip("lightgbm")


def _fit_pred(X_tr, y_tr, X_te, seed=0):
    model = train_lightgbm(X_tr, y_tr, seed=seed, num_threads=1)
    return predict(model["booster"], X_te), model


def _drift_data(n_per_month=200, months=12, seed=7):
    """Monthly **concept-reversal** drift (the worst case for time-aware).

    Month m: benign feature mean = +m·shift − C, malware mean = +m·shift + C
    on feature 0, with a constant class gap on features 1..3 that flips sign
    every few months. Early months look like late months of the *opposite*
    labeling, so a model trained only on early months is actively wrong on
    late months, while a random-split model sees every month in train and
    test and averages cleanly. That is precisely the RQ1 bias direction:
    random splits overstate deployable performance.
    """
    rng = np.random.default_rng(seed)
    Xs, ys, ts = [], [], []
    t0 = 1_600_000_000  # 2020-09
    month = 30 * 24 * 3600
    for m in range(months):
        n = n_per_month
        shift = 0.8 * m
        flip = (-1.0) ** (m // 3)  # the stable class signal reverses every 3 months
        f0 = np.concatenate(
            [rng.standard_normal((n, 1)) * 0.5 + shift - 2.0,
             rng.standard_normal((n, 1)) * 0.5 + shift + 2.0]
        )
        rest = rng.standard_normal((2 * n, 3))
        rest += flip * np.concatenate([np.full((n, 3), 2.0), np.full((n, 3), -2.0)])
        X = np.concatenate([f0, rest], axis=1).astype(np.float32)
        y = np.array([0] * n + [1] * n, dtype=np.int64)
        ts.extend([t0 + m * month] * (2 * n))
        Xs.append(X)
        ys.append(y)
    return np.concatenate(Xs), np.concatenate(ys), ts


class TestTrainPredict:
    def test_separable_data_is_perfect(self) -> None:
        rng = np.random.default_rng(0)
        X = rng.standard_normal((400, 6)).astype(np.float32)
        y = (X[:, 0] > 0).astype(np.int64)
        pred, model = _fit_pred(X, y, X)
        assert macro_f1(y, pred) > 0.95
        assert model["model_artifact_sha256"] is not None

    def test_seed_affects_nothing_on_this_deterministic_setup(self) -> None:
        """Same data + same params: two seeds give identical predictions
        (full determinism; LightGBM histogram mode, single thread)."""
        rng = np.random.default_rng(1)
        X = rng.standard_normal((300, 5)).astype(np.float32)
        y = (X[:, 0] + 0.5 * X[:, 1] > 0).astype(np.int64)
        pred_a, _ = _fit_pred(X, y, X, seed=0)
        pred_b, _ = _fit_pred(X, y, X, seed=0)
        assert (pred_a == pred_b).all()


class TestSanityShuffledLabels:
    """Sanity test 1: shuffled labels ⇒ near-chance macro-F1."""

    def test_shuffled_labels_near_chance(self) -> None:
        rng = np.random.default_rng(3)
        X = rng.standard_normal((400, 5)).astype(np.float32)
        X_tr, X_te = X[:300], X[300:]
        y_tr_shuffled = rng.permutation(X[:300][:, 0] > 0).astype(np.int64)
        pred, _ = _fit_pred(X_tr, y_tr_shuffled, X_te)
        assert macro_f1(X[300:, 0] > 0, pred) < 0.55


class TestSanitySplitGap:
    """Sanity test 2: random-split score > time-aware score on drift data."""

    def test_random_beats_time_aware_on_synthetic_drift(self) -> None:
        X, y, ts = _drift_data(n_per_month=150, months=10)
        ids = [f"{i:064x}" for i in range(len(y))]
        fam_strata = y.astype(str)  # stratify by label for the random split

        rand = random_split(ids=ids, strata=fam_strata, seed=11)
        ta = time_aware_split(ids=ids, timestamps=ts)

        idx = {i: k for k, i in enumerate(ids)}
        tr = np.array([idx[i] for i in rand["train"]])
        te = np.array([idx[i] for i in rand["test"]])
        pred_rand, _ = _fit_pred(X[tr], y[tr], X[te])
        f1_rand = macro_f1(y[te], pred_rand)

        tr_t = np.array([idx[i] for i in ta["train"]])
        te_t = np.array([idx[i] for i in ta["test"]])
        pred_ta, _ = _fit_pred(X[tr_t], y[tr_t], X[te_t])
        f1_ta = macro_f1(y[te_t], pred_ta)

        assert f1_rand > f1_ta + 0.05, (
            f"expected a visible RQ1 gap on synthetic drift; got random={f1_rand:.3f} "
            f"time_aware={f1_ta:.3f}"
        )


class TestConfigDriven:
    def test_model_name_and_params(self) -> None:
        assert MODEL_NAME == "lightgbm"
        model = train_lightgbm(
            np.zeros((10, 2), dtype=np.float32),
            np.zeros(10, dtype=np.int64),
            seed=0,
            params={"num_boost_round": 5},
            num_threads=1,
        )
        assert model["resolved_params"]["seed"] == 0
        assert model["resolved_params"]["num_boost_round"] == 5
        assert model["resolved_params"]["num_threads"] == 1
