"""Unit tests for paper.tables (ADR-009).

Acceptance test 8 (prompt): the table generator rejects ``smoke`` and
``pilot-10pct`` runs. Also covers test-window/lock refusals, artifact
contents, and the build manifest.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from logger import RunRecorder, append_jsonl
from logger.hashing import hash_object
from paper.tables import RefusedRun, eligible_runs, generate_table_artifact
from runner.locks import freeze, lock_hash


def _seed_record(
    path: Path,
    run_id: str,
    cfg: dict,
    seed: int,
    *,
    tags: list[str] | None = None,
    test_touched: bool = False,
    test_lock_hash: str | None = None,
) -> None:
    r = RunRecorder(Path("unused"))
    rec = r.start(
        cfg,
        seed,
        "malconv",
        tags=tags,
        test_touched=test_touched,
        test_lock_hash=test_lock_hash,
        existing_run_id=run_id,
    )
    append_jsonl(RunRecorder.finish(rec, {"accuracy": 0.9}, 1.0), path)


@pytest.fixture()
def env(tmp_path: Path):
    """(records.jsonl, frozen dir) with one clean eligible run."""
    path = tmp_path / "records.jsonl"
    _seed_record(path, "clean0001aaaa", {"model": "malconv"}, 42)
    frozen = tmp_path / "frozen"
    frozen.mkdir()
    return path, frozen


class TestEligibility:
    def test_clean_runs_pass(self, env) -> None:
        path, frozen = env
        runs = eligible_runs(_read(path), frozen)
        assert [r.run_id for r in runs] == ["clean0001aaaa"]

    def test_smoke_tag_refused(self, env) -> None:
        """Acceptance test 8."""
        path, frozen = env
        _seed_record(path, "smoke000bbbb", {"model": "cnn"}, 1, tags=["smoke"])
        with pytest.raises(RefusedRun, match="smoke"):
            eligible_runs(_read(path), frozen)

    def test_pilot_tag_refused(self, env) -> None:
        path, frozen = env
        _seed_record(path, "pilot00cccccc", {"model": "cnn"}, 2, tags=["pilot-10pct"])
        with pytest.raises(RefusedRun, match="pilot-10pct"):
            eligible_runs(_read(path), frozen)

    def test_test_touched_without_lock_refused(self, env) -> None:
        path, frozen = env
        _seed_record(path, "test0000dddd", {"model": "cnn"}, 3, test_touched=True)
        with pytest.raises(RefusedRun, match="no freeze lock"):
            eligible_runs(_read(path), frozen)

    def test_test_touched_with_matching_lock_passes(self, env) -> None:
        path, frozen = env
        _seed_record(path, "test1111eeee", {"model": "cnn"}, 4, test_touched=True)
        rec = _read(path)[1]
        # Freeze a lock and stamp the run with exactly its hash.
        lock_path = freeze(
            "pilot",
            config_hash=rec.config_hash,
            split_hash="s" * 64,
            dataset_hash="d" * 64,
            git_sha="abc",
            frozen_dir=frozen,
        )
        lock = json.loads(lock_path.read_text(encoding="utf-8"))
        path.write_text("", encoding="utf-8")  # rewrite seeded records with the stamp
        _seed_record(path, "clean0001aaaa", {"model": "malconv"}, 42)
        _seed_record(
            path,
            "test1111eeee",
            {"model": "cnn"},
            4,
            test_touched=True,
            test_lock_hash=lock_hash(lock),
        )
        runs = eligible_runs(_read(path), frozen)
        assert [r.run_id for r in runs] == ["clean0001aaaa", "test1111eeee"]

    def test_wrong_lock_hash_refused(self, env) -> None:
        path, frozen = env
        _seed_record(
            path,
            "test2222ffff",
            {"model": "cnn"},
            5,
            test_touched=True,
            test_lock_hash="0" * 64,
        )
        with pytest.raises(RefusedRun, match="no freeze lock"):
            eligible_runs(_read(path), frozen)


class TestArtifact:
    def test_artifact_contents_and_manifest(self, env, tmp_path: Path) -> None:
        path, frozen = env
        art = generate_table_artifact(
            "tab1",
            path,
            ["clean0001aaaa"],
            frozen_dir=frozen,
            artifacts_dir=tmp_path / "artifacts",
        )
        assert art["run_ids"] == ["clean0001aaaa"]
        assert art["run_hashes"][0]["record_hash"] is not None
        assert art["aggregate"]["n_runs"] == 1
        assert "accuracy" in art["aggregate"]["metric_names"]
        assert art["output_sha256"] == hash_object(
            {k: v for k, v in art.items() if k != "output_sha256"}
        )
        # The manifest lives next to the artifacts dir (paper/build_manifest.json
        # in production; here artifacts_dir=tmp_path/artifacts).
        manifest = json.loads((tmp_path / "build_manifest.json").read_text(encoding="utf-8"))
        assert manifest["artifacts"]["tab1"]["run_ids"] == ["clean0001aaaa"]

    def test_artifact_refuses_smoke_run(self, env, tmp_path: Path) -> None:
        path, frozen = env
        _seed_record(path, "smoke000bbbb", {"model": "cnn"}, 1, tags=["smoke"])
        with pytest.raises(RefusedRun, match="smoke"):
            generate_table_artifact(
                "tab2",
                path,
                ["smoke000bbbb"],
                frozen_dir=frozen,
                artifacts_dir=tmp_path / "artifacts",
            )

    def test_missing_run_id_refused(self, env, tmp_path: Path) -> None:
        path, frozen = env
        with pytest.raises(RefusedRun, match="not found"):
            generate_table_artifact(
                "tab3",
                path,
                ["nope0nope0nope"],
                frozen_dir=frozen,
                artifacts_dir=tmp_path / "artifacts",
            )


def _read(path: Path):
    from logger.run_records import read_jsonl

    return read_jsonl(path)
