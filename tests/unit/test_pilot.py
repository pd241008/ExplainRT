"""Unit tests for runner.pilot (ADR-010 §5 rev 2).

Synthetic BODMAS-shaped npz only. Guards: val-side-only evaluation
(``test_touched=False``), npz-only split protocols (``time_aware`` raises),
AUT recorded as ``null`` (never invented), and the ``pilot-10pct`` tag
contract in the config.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest
import yaml
from runner.pilot import PILOT_TAG, _split_10pct, run_pilot


@pytest.fixture(scope="module")
def pilot_config() -> dict:
    cfg = yaml.safe_load(Path("configs/p1_prelim_r1_bodmas.yaml").read_text())
    assert cfg["model"] == "lightgbm"
    assert PILOT_TAG in cfg["runner"]["tags"]
    assert cfg["runner"]["test_touched"] is False
    return cfg


@pytest.fixture(scope="module")
def synthetic(monkeypatch_module) -> dict:
    """Patch load_bodmas to a synthetic BODMAS-shaped dataset."""
    return {}


@pytest.fixture(scope="module")
def monkeypatch_module():
    """Module-scoped empty fixture (keeps fixture order simple)."""
    yield


@pytest.fixture()
def patch_data(monkeypatch):
    """A separable synthetic dataset (300 rows, 8 features)."""
    rng = np.random.default_rng(0)
    X = rng.standard_normal((300, 8)).astype(np.float32)
    y = (X[:, 0] > 0).astype(np.int64)
    calls = {"n": 0}

    def fake_load():
        from bytelens.data.bodmas import BODMASData, DataMode
        from logger.hashing import hash_array

        return BODMASData(
            X=X,
            y=y,
            mode=DataMode.NPZ_ONLY,
            npz_sha256="a" * 64,
            feature_hash=hash_array(X),
            npz_files=["X", "y"],
        )

    import bytelens.data.bodmas as bod

    monkeypatch.setattr(bod, "load_bodmas", fake_load)
    import runner.pilot as pilot

    monkeypatch.setattr(pilot, "BODMASData", bod.BODMASData)
    monkeypatch.setattr(pilot, "load_bodmas", lambda: fake_load())
    calls["n"] += 1
    return X, y


class TestSplit10Pct:
    def test_random_protocol_partitions(self, patch_data) -> None:
        X, y = patch_data
        from bytelens.data.bodmas import load_bodmas

        data = load_bodmas()
        sides, info = _split_10pct(data, protocol="random", seed=0)
        ids = data.row_ids()
        union = sorted([*sides["train"], *sides["val"], *sides["test"]])
        assert len(union) == round(0.10 * len(ids))
        assert info["sampling_fraction"] == 0.10
        assert not ({*sides["train"]} & {*sides["val"]})
        assert not ({*sides["val"]} & {*sides["test"]})

    def test_proxy_protocol_partitions(self, patch_data) -> None:
        X, y = patch_data
        from bytelens.data.bodmas import load_bodmas

        data = load_bodmas()
        sides, _ = _split_10pct(data, protocol="near_duplicate_proxy", seed=0)
        union = sorted([*sides["train"], *sides["val"], *sides["test"]])
        assert len(union) >= 1
        assert not ({*sides["train"]} & {*sides["val"]})

    def test_time_aware_raises_npzonly(self, patch_data) -> None:
        from bytelens.data.bodmas import load_bodmas

        data = load_bodmas()
        with pytest.raises(ValueError, match="time_aware"):
            _split_10pct(data, protocol="time_aware", seed=0)


class TestRunPilot:
    def test_val_only_metrics_and_aut_null(self, patch_data, pilot_config) -> None:
        cfg = dict(pilot_config)
        cfg["split_protocol"] = "random"
        metrics, details = run_pilot(cfg, seed=0)
        assert metrics["val/aut"] is None  # never invented in npz-only mode
        assert 0.0 <= metrics["val/macro_f1"] <= 1.0
        assert details["test_touched"] is False
        assert details["eval_side"] == "val"
        assert details["train_n"] > 0

    def test_separable_data_beats_chance(self, patch_data, pilot_config) -> None:
        # At the default 10% fraction the synthetic val side is ~4 rows —
        # too small for a stability assertion. 50% keeps it synthetic but
        # checks the learning signal itself.
        cfg = dict(pilot_config)
        cfg["split_protocol"] = "random"
        cfg["pilot"] = {"fraction": 0.5}
        metrics, details = run_pilot(cfg, seed=0)
        assert details["train_n"] >= 50
        assert metrics["val/macro_f1"] > 0.6

    def test_deterministic_per_seed(self, patch_data, pilot_config) -> None:
        cfg = dict(pilot_config)
        cfg["split_protocol"] = "near_duplicate_proxy"
        a, _ = run_pilot(cfg, seed=3)
        b, _ = run_pilot(cfg, seed=3)
        assert a["val/macro_f1"] == b["val/macro_f1"]
