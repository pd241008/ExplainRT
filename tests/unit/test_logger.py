"""Unit tests for logger/ run records (P0).

Covers the AGENTS.md section 8 contract: identity fields exist, config
hashing is deterministic and order-insensitive, JSONL round-trips, and
nothing is ever fabricated (missing values are None, not guesses).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from logger import (
    RunRecord,
    RunRecorder,
    append_jsonl,
    capture_env,
    config_hash,
    read_jsonl,
)

CONFIG_A = {"model": "malconv", "seed": 42, "attack": "A1"}
CONFIG_A_REORDERED = {"attack": "A1", "seed": 42, "model": "malconv"}
CONFIG_B = {"model": "malconv", "seed": 43, "attack": "A1"}


class TestConfigHash:
    def test_deterministic(self) -> None:
        assert config_hash(CONFIG_A) == config_hash(CONFIG_A)

    def test_key_order_independent(self) -> None:
        assert config_hash(CONFIG_A) == config_hash(CONFIG_A_REORDERED)

    def test_sensitive_to_values(self) -> None:
        assert config_hash(CONFIG_A) != config_hash(CONFIG_B)

    def test_is_sha256_hex(self) -> None:
        h = config_hash(CONFIG_A)
        assert len(h) == 64
        int(h, 16)  # must parse as hex


class TestRunRecord:
    def test_start_fills_identity_fields(self) -> None:
        rec = RunRecorder(output_dir=Path("unused")).start(
            config=CONFIG_A, seed=42, model_name="malconv"
        )
        assert rec.run_id
        assert rec.created.endswith("Z")
        assert rec.config_hash == config_hash(CONFIG_A)
        assert rec.seed == 42
        assert rec.model_name == "malconv"
        assert rec.metrics == {}

    def test_finish_sets_metrics_and_wall_time(self) -> None:
        rec = RunRecorder(Path("unused")).start(CONFIG_A, 42, "malconv")
        out = RunRecorder.finish(rec, metrics={"accuracy": 0.9}, wall_time_sec=1.5)
        assert out.metrics == {"accuracy": 0.9}
        assert out.wall_time_sec == 1.5

    def test_json_round_trip(self) -> None:
        rec = RunRecorder(Path("unused")).start(CONFIG_A, 42, "malconv")
        rec = RunRecorder.finish(rec, {"f1": 0.5}, 10.0)
        raw = json.loads(rec.to_json())
        assert RunRecord.from_dict(raw) == rec

    def test_from_dict_rejects_missing_fields(self) -> None:
        with pytest.raises(ValueError, match="missing required fields"):
            RunRecord.from_dict({"run_id": "x"})

    def test_two_starts_get_distinct_run_ids(self) -> None:
        r = RunRecorder(Path("unused"))
        a = r.start(CONFIG_A, 42, "malconv")
        b = r.start(CONFIG_A, 42, "malconv")
        assert a.run_id != b.run_id


class TestJsonlPersistence:
    def test_append_and_read_round_trip(self, tmp_path: Path) -> None:
        rec = RunRecorder(tmp_path).start(CONFIG_A, 42, "cnn")
        rec = RunRecorder.finish(rec, {"acc": 1.0}, 0.1)
        path = append_jsonl(rec, tmp_path / "runs.jsonl")
        assert read_jsonl(path) == [rec]

    def test_append_preserves_prior_lines(self, tmp_path: Path) -> None:
        r1 = RunRecorder(tmp_path).start(CONFIG_A, 42, "cnn")
        r2 = RunRecorder(tmp_path).start(CONFIG_B, 43, "resnet")
        path = tmp_path / "runs.jsonl"
        append_jsonl(r1, path)
        append_jsonl(r2, path)
        assert len(read_jsonl(path)) == 2


class TestCaptureEnv:
    def test_has_core_fields(self) -> None:
        env = capture_env()
        assert set(env) == {"python", "platform", "machine", "cpu_count", "gpu"}
        assert isinstance(env["python"], str)

    def test_gpu_is_none_without_torch_or_list_with(self) -> None:
        env = capture_env()
        assert env["gpu"] is None or isinstance(env["gpu"], list)
