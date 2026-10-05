"""Unit tests for runner.execution (ADR-009).

Acceptance test 10 (prompt): two runs with the same seed reproduce identical
metrics on the toy pipeline.
"""

from __future__ import annotations

import pytest
from runner.execution import resolve_pipeline_config, run_pipeline

CFG = {"n_samples": 64, "n_features": 4, "distribution": "normal"}


class TestReproducibility:
    def test_same_seed_identical_metrics(self) -> None:
        """Acceptance test 10."""
        m1, d1 = run_pipeline(CFG, seed=42)
        m2, d2 = run_pipeline(CFG, seed=42)
        assert m1 == m2  # bitwise identical floats
        assert d1["data_hash"] == d2["data_hash"]

    def test_different_seed_different_metrics(self) -> None:
        m1, _ = run_pipeline(CFG, seed=42)
        m2, _ = run_pipeline(CFG, seed=43)
        assert m1 != m2

    def test_config_change_changes_metrics(self) -> None:
        m1, _ = run_pipeline(CFG, seed=42)
        m2, _ = run_pipeline({**CFG, "distribution": "uniform"}, seed=42)
        assert m1 != m2


class TestResolveConfig:
    def test_defaults_applied(self) -> None:
        resolved = resolve_pipeline_config({})
        assert resolved == {"n_samples": 256, "n_features": 8, "distribution": "normal"}

    def test_config_wins_over_defaults(self) -> None:
        assert resolve_pipeline_config({"n_samples": 10})["n_samples"] == 10

    def test_none_values_become_defaults(self) -> None:
        assert resolve_pipeline_config({"n_samples": None})["n_samples"] == 256

    def test_invalid_values_rejected(self) -> None:
        with pytest.raises(ValueError, match="positive"):
            resolve_pipeline_config({"n_samples": 0})
        with pytest.raises(ValueError, match="distribution"):
            resolve_pipeline_config({"distribution": "cauchy"})
