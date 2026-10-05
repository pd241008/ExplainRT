"""Unit tests for the ADR-009 CLIs: logger.trace, logger.verify, logger.repro.

Acceptance test 9 (prompt): ``logger.trace`` returns the full chain for a
fixture table cell (an artifact id built from seeded fixture runs).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from logger.repro import compare_metrics, load_run, reproduce
from logger.run_records import RunRecorder, append_jsonl, read_jsonl
from logger.trace import format_run
from logger.trace import main as trace_main
from logger.verify import run_all_checks
from runner.execution import run_pipeline


@pytest.fixture()
def traced_env(tmp_path: Path, monkeypatch) -> tuple[Path, Path]:
    """A records file with one run + an artifact referencing it, with paths
    monkeypatched so the CLIs operate inside tmp_path."""
    records = tmp_path / "runs.jsonl"
    cfg = {"n_samples": 32, "n_features": 2, "distribution": "normal"}
    rec = RunRecorder(tmp_path).start(cfg, 42, "toy")
    metrics, _ = run_pipeline(cfg, 42)
    append_jsonl(RunRecorder.finish(rec, metrics, 0.5), records)

    from logger.hashing import hash_object

    artifact = {
        "table_id": "tab_fixture",
        "run_ids": [rec.run_id],
        "output_sha256": hash_object({"runs": [rec.run_id]}),
        "aggregate": {"n_runs": 1},
    }
    art_dir = tmp_path / "artifacts"
    art_dir.mkdir()
    (art_dir / "tab_fixture.json").write_text(json.dumps(artifact), encoding="utf-8")
    return records, art_dir


class TestTrace:
    """Acceptance test 9: full chain for a fixture table cell."""

    def test_trace_artifact_prints_full_chain(
        self, traced_env: tuple[Path, Path], capsys, monkeypatch
    ) -> None:
        records, art_dir = traced_env
        monkeypatch.setattr("logger.trace.ARTIFACTS_DIR", art_dir)
        monkeypatch.setattr("logger.trace.RECORDS_PATH", records)
        rc = trace_main(["tab_fixture"])
        assert rc == 0
        out = capsys.readouterr().out
        assert "tab_fixture" in out
        # the full chain elements are present
        assert "git_sha" in out
        assert "record_hash" in out
        assert "repro" in out  # reproduction command printed

    def test_trace_run_id_prints_chain(
        self, traced_env: tuple[Path, Path], capsys, monkeypatch
    ) -> None:
        records, _ = traced_env
        monkeypatch.setattr("logger.trace.RECORDS_PATH", records)
        recs = read_jsonl(records)
        assert trace_main([recs[0].run_id]) == 0
        out = capsys.readouterr().out
        assert recs[0].run_id in out
        assert str(recs[0].seed) in out
        assert "record_hash" in out

    def test_trace_missing_target_fails(self, capsys, monkeypatch) -> None:
        monkeypatch.setattr("logger.trace.RECORDS_PATH", Path("/nonexistent/records.jsonl"))
        with pytest.raises(SystemExit) as exc:
            trace_main(["missing0thing"])
        assert exc.value.code == 1
        assert "no run records found" in capsys.readouterr().err

    def test_format_run_covers_chain_fields(self, traced_env: tuple[Path, Path]) -> None:
        records, _ = traced_env
        from logger.run_records import read_jsonl

        rec = read_jsonl(records)[0]
        text = "\n".join(format_run(rec))
        for field in (
            "run_id",
            "created",
            "config_hash",
            "dataset_hash",
            "git_sha",
            "requirements",
            "record_hash",
            "reproduce",
        ):
            assert field in text


class TestVerify:
    def test_all_checks_pass_or_na(self, tmp_path: Path) -> None:
        # Empty manifest + no splits + no records → all N/A, exit ok.
        manifest = tmp_path / "MANIFEST.json"
        manifest.write_text(json.dumps({"schema_version": 1, "files": []}), encoding="utf-8")
        ok, fail = run_all_checks(
            manifest_path=manifest,
            raw_dir=tmp_path / "raw",
            splits_dir=tmp_path / "splits",
            records_path=tmp_path / "absent.jsonl",
        )
        assert fail == []
        assert any("N/A" in line for line in ok)

    def test_broken_chain_is_reported(self, tmp_path: Path) -> None:
        records = tmp_path / "runs.jsonl"
        r = RunRecorder(tmp_path)
        cfg = {"n_samples": 8, "n_features": 2, "distribution": "uniform"}
        rec1 = r.start(cfg, 1, "toy")
        append_jsonl(RunRecorder.finish(rec1, {"m": 0.1}, 0.1), records)
        rec2 = r.start(cfg, 2, "toy")
        append_jsonl(RunRecorder.finish(rec2, {"m": 0.2}, 0.1), records)
        lines = records.read_text(encoding="utf-8").splitlines()
        tampered = json.loads(lines[0])
        tampered["metrics"]["m"] = 0.99
        lines[0] = json.dumps(tampered, sort_keys=True, separators=(",", ":"))
        records.write_text("\n".join(lines) + "\n", encoding="utf-8")

        ok, fail = run_all_checks(
            manifest_path=tmp_path / "absent.json",
            splits_dir=tmp_path / "splits",
            records_path=records,
        )
        assert any("record" in f for f in fail)

    def test_manifest_mismatch_is_reported(self, tmp_path: Path) -> None:
        raw = tmp_path / "raw"
        raw.mkdir()
        (raw / "x.bin").write_bytes(b"hello")
        entry = {
            "logical_name": "x",
            "path": "x.bin",
            "source_url": "u",
            "retrieval_date": "2026-10-05",
            "size_bytes": 5,
            "sha256": "0" * 64,  # wrong on purpose
            "license_note": "fixture",
        }
        manifest = tmp_path / "MANIFEST.json"
        manifest.write_text(json.dumps({"schema_version": 1, "files": [entry]}), encoding="utf-8")
        ok, fail = run_all_checks(
            manifest_path=manifest,
            raw_dir=raw,
            splits_dir=tmp_path / "splits",
            records_path=tmp_path / "absent.jsonl",
        )
        assert any("MISMATCH" in f for f in fail)


class TestRepro:
    def test_same_seed_reproduces(self, traced_env: tuple[Path, Path]) -> None:
        records, _ = traced_env
        rec = load_run(_only_run(records), records)
        ok, problems, fresh = reproduce(rec)
        assert ok and problems == [] and fresh == rec.metrics

    def test_tampered_metrics_fail_repro(self, traced_env: tuple[Path, Path]) -> None:
        records, _ = traced_env
        from logger.run_records import read_jsonl

        rec = read_jsonl(records)[0]
        rec.metrics = {k: v + 1.0 for k, v in rec.metrics.items()}
        ok, problems, _ = reproduce(rec)
        assert not ok
        assert any("MISMATCH" in p for p in problems)

    def test_compare_metrics_tolerance_stated(self, capsys) -> None:
        ok, problems = compare_metrics({"a": 1.0}, {"a": 1.0 + 1e-12}, tolerance=1e-9)
        assert ok and problems == []  # within tolerance passes...
        assert "tolerance" in capsys.readouterr().out  # ...but is stated
        ok2, problems2 = compare_metrics({"a": 1.0}, {"a": 2.0}, tolerance=1e-9)
        assert not ok2 and any("MISMATCH" in p for p in problems2)

    def test_missing_metric_detected(self) -> None:
        ok, problems = compare_metrics({"a": 1.0, "b": 2.0}, {"a": 1.0}, tolerance=0.0)
        assert not ok and any("missing from reproduction" in p for p in problems)


def _only_run(records: Path) -> str:
    from logger.run_records import read_jsonl

    return read_jsonl(records)[0].run_id
