"""Unit tests for ADR-009 run-record upgrades.

Acceptance test 4 (prompt): run IDs are deterministic for identical inputs
and differ when any input changes.
Acceptance test 5 (prompt): the record chain detects an edited or deleted
line. Also covers the new provenance fields (git dirty, tags, test_touched,
seeds) and schema-v2 round-trips.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from logger import (
    RunRecorder,
    append_jsonl,
    compute_record_hash,
    derivable_run_id,
    read_jsonl,
    verify_chain,
)

CFG = {"experiment": "p0_smoke", "model": "malconv", "seed": 42}
BASE = {
    "config_hash": "c" * 64,
    "dataset_hash": "d" * 64,
    "split_hash": "s" * 64,
    "git_sha": "abc123def456",
    "seed": 42,
}


class TestDerivedRunId:
    """Acceptance test 4."""

    def test_deterministic_for_identical_inputs(self) -> None:
        assert derivable_run_id(**BASE) == derivable_run_id(**BASE)

    def test_differs_when_any_input_changes(self) -> None:
        base = derivable_run_id(**BASE)
        assert derivable_run_id(**{**BASE, "config_hash": "c" * 63 + "0"}) != base
        assert derivable_run_id(**{**BASE, "dataset_hash": "d" * 63 + "0"}) != base
        assert derivable_run_id(**{**BASE, "split_hash": "s" * 63 + "0"}) != base
        assert derivable_run_id(**{**BASE, "git_sha": "abc123def457"}) != base
        assert derivable_run_id(**{**BASE, "seed": 43}) != base

    def test_none_inputs_contribute_but_stay_deterministic(self) -> None:
        a = derivable_run_id(None, None, None, None, 0)
        b = derivable_run_id(None, None, None, None, 0)
        assert a == b and len(a) == 12

    def test_is_12_hex_chars(self) -> None:
        rid = derivable_run_id(**BASE)
        assert len(rid) == 12
        int(rid, 16)

    def test_recorder_uses_derived_id(self) -> None:
        rec = RunRecorder(Path("unused")).start(CFG, 42, "malconv")
        expected = derivable_run_id(
            rec.config_hash, rec.dataset_hash, rec.dataset_split_hash, rec.git_sha, 42
        )
        assert rec.run_id == expected


class TestRecordChain:
    """Acceptance test 5."""

    def _write_two_records(self, tmp_path: Path) -> Path:
        path = tmp_path / "runs.jsonl"
        r = RunRecorder(tmp_path)
        rec1 = r.start(CFG, 42, "malconv")
        append_jsonl(RunRecorder.finish(rec1, {"acc": 0.5}, 1.0), path)
        rec2 = r.start(CFG, 43, "malconv")
        append_jsonl(RunRecorder.finish(rec2, {"acc": 0.6}, 1.0), path)
        return path

    def test_chain_links_records(self, tmp_path: Path) -> None:
        path = self._write_two_records(tmp_path)
        lines = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
        assert lines[0]["prev_record_hash"] is None
        assert lines[1]["prev_record_hash"] == lines[0]["record_hash"]
        for line in lines:
            assert line["record_hash"] == compute_record_hash(line)

    def test_verify_chain_ok(self, tmp_path: Path) -> None:
        path = self._write_two_records(tmp_path)
        assert verify_chain(path) == []
        assert read_jsonl(path, check_chain=True)

    def test_edited_line_detected(self, tmp_path: Path) -> None:
        path = self._write_two_records(tmp_path)
        lines = path.read_text(encoding="utf-8").splitlines()
        tampered = json.loads(lines[0])
        tampered["metrics"]["acc"] = 0.99  # the classic fraud
        lines[0] = json.dumps(tampered, sort_keys=True, separators=(",", ":"))
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        problems = verify_chain(path)
        assert any("record_hash mismatch" in p for p in problems)
        # from_dict rejects the edited record on sight...
        with pytest.raises(ValueError, match="record was modified"):
            read_jsonl(path)
        # ...and the chain check catches it as well.
        with pytest.raises(ValueError, match="chain broken|record was modified"):
            read_jsonl(path, check_chain=True)

    def test_deleted_line_detected(self, tmp_path: Path) -> None:
        path = self._write_two_records(tmp_path)
        lines = path.read_text(encoding="utf-8").splitlines()
        path.write_text(lines[1] + "\n", encoding="utf-8")  # drop record 1
        problems = verify_chain(path)
        assert any("prev_record_hash mismatch" in p for p in problems)

    def test_from_dict_rejects_modified_record(self, tmp_path: Path) -> None:
        path = self._write_two_records(tmp_path)
        rec = read_jsonl(path)[0]
        raw = rec.to_dict()
        raw["metrics"]["acc"] = 1.0  # tamper after sealing
        from logger import RunRecord

        with pytest.raises(ValueError, match="record_hash mismatch"):
            RunRecord.from_dict(raw)


class TestProvenanceFields:
    def test_seeds_expanded(self) -> None:
        rec = RunRecorder(Path("unused")).start(CFG, 42, "malconv")
        assert rec.seeds == {"python": 42, "numpy": 42, "framework": 42}

    def test_tags_and_test_touched_recorded(self) -> None:
        rec = RunRecorder(Path("unused")).start(
            CFG,
            42,
            "malconv",
            tags=["final"],
            test_touched=True,
            test_lock_hash="L" * 64,
        )
        assert rec.tags == ["final"]
        assert rec.test_touched is True
        assert rec.test_lock_hash == "L" * 64

    def test_git_context_captured(self) -> None:
        rec = RunRecorder(Path("unused")).start(CFG, 42, "malconv", repo_dir=Path.cwd())
        # Inside the real repo we have a SHA; dirty may be either.
        assert rec.git_sha is not None
        assert rec.branch is not None
        assert isinstance(rec.git_dirty, bool)

    def test_v1_records_still_load(self) -> None:
        """ADR-007-era records (timestamp+uuid run_id, no chain) stay readable."""
        legacy = {
            "run_id": "20261001-120000-abcd1234",
            "created": "2026-10-01T12:00:00Z",
            "config_hash": "c" * 64,
            "config": {"model": "cnn"},
            "git_sha": None,
            "seed": 0,
            "dataset_split_hash": None,
            "model_name": "cnn",
            "metrics": {},
            "wall_time_sec": 0.0,
            "hardware": {},
            "requirements_hash": None,
        }
        from logger import RunRecord

        parsed = RunRecord.from_dict(legacy)
        assert parsed.run_id == "20261001-120000-abcd1234"
        assert parsed.record_hash is None  # v1: no chain yet

    def test_unknown_fields_rejected(self) -> None:
        from logger import RunRecord

        legacy = {
            "run_id": "x",
            "created": "t",
            "config_hash": "c",
            "config": {},
            "git_sha": None,
            "seed": 0,
            "dataset_split_hash": None,
            "model_name": "m",
            "metrics": {},
            "wall_time_sec": 0.0,
            "hardware": {},
            "requirements_hash": None,
            "teleports": True,
        }
        with pytest.raises(ValueError, match="unknown fields"):
            RunRecord.from_dict(legacy)
