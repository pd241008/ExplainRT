"""Unit tests for runner/ planning (P0).

Covers the hard rule "seeds are fixed in config, never in code": seed
expansion comes only from the YAML ``seeds`` list, one deep copy each,
identical except the seed. Also covers resume identity semantics.
"""

from __future__ import annotations

import pytest
import yaml
from logger.run_records import RunRecorder
from runner import (
    PlannedRun,
    expand_seeds,
    load_config,
    plan_from_config,
    resume_filter,
)

BASE_CONFIG = {
    "experiment": "p0_smoke",
    "model": "baseline_cnn",
    "seeds": [0, 1, 2],
    "render": {"width_bucket": 224, "pad_value": 0},
}


class TestLoadConfig:
    def test_round_trip_from_yaml(self, tmp_path) -> None:
        p = tmp_path / "exp.yaml"
        p.write_text(yaml.safe_dump(BASE_CONFIG), encoding="utf-8")
        assert load_config(p) == BASE_CONFIG

    def test_rejects_non_mapping(self, tmp_path) -> None:
        p = tmp_path / "bad.yaml"
        p.write_text("- just\n- a\n- list\n", encoding="utf-8")
        with pytest.raises(ValueError, match="must be a YAML mapping"):
            load_config(p)

    def test_rejects_missing_keys(self, tmp_path) -> None:
        p = tmp_path / "bad.yaml"
        p.write_text(yaml.safe_dump({"experiment": "x"}), encoding="utf-8")
        with pytest.raises(ValueError, match="missing required keys"):
            load_config(p)

    def test_rejects_empty_seed_list(self, tmp_path) -> None:
        cfg = {**BASE_CONFIG, "seeds": []}
        p = tmp_path / "bad.yaml"
        p.write_text(yaml.safe_dump(cfg), encoding="utf-8")
        with pytest.raises(ValueError, match="non-empty list"):
            load_config(p)

    def test_rejects_non_int_seeds(self, tmp_path) -> None:
        cfg = {**BASE_CONFIG, "seeds": [0, "1"]}
        p = tmp_path / "bad.yaml"
        p.write_text(yaml.safe_dump(cfg), encoding="utf-8")
        with pytest.raises(ValueError, match="only ints"):
            load_config(p)

    def test_rejects_bool_seeds(self) -> None:
        # bool is an int subclass in Python; it must not count as a seed.
        with pytest.raises(ValueError, match="only ints"):
            expand_seeds({**BASE_CONFIG, "seeds": [True]})


class TestExpandSeeds:
    def test_one_config_per_seed(self) -> None:
        out = expand_seeds(BASE_CONFIG)
        assert len(out) == 3
        assert [c["seed"] for c in out] == [0, 1, 2]

    def test_only_seed_differs(self) -> None:
        out = expand_seeds(BASE_CONFIG)
        stripped = [{k: v for k, v in c.items() if k != "seed"} for c in out]
        assert stripped[0] == stripped[1] == stripped[2]

    def test_source_config_not_mutated(self) -> None:
        snapshot = yaml.safe_dump(BASE_CONFIG)
        expand_seeds(BASE_CONFIG)
        assert yaml.safe_dump(BASE_CONFIG) == snapshot

    def test_order_and_duplicates_preserved(self) -> None:
        out = expand_seeds({**BASE_CONFIG, "seeds": [2, 2, 0]})
        assert [c["seed"] for c in out] == [2, 2, 0]


class TestPlan:
    def test_plan_is_deterministic(self) -> None:
        assert plan_from_config(BASE_CONFIG) == plan_from_config(BASE_CONFIG)

    def test_config_hash_matches_logger(self) -> None:
        from logger import config_hash

        plan = plan_from_config(BASE_CONFIG)
        assert plan[0].config_hash == config_hash(plan[0].config)

    def test_distinct_seeds_distinct_hashes(self) -> None:
        plan = plan_from_config(BASE_CONFIG)
        assert len({p.config_hash for p in plan}) == 3


class TestResume:
    def _record_for(self, planned: PlannedRun, recorder) -> None:
        rec = recorder.start(
            config=planned.config, seed=planned.seed, model_name=planned.model_name
        )
        return RunRecorder.finish(rec, metrics={}, wall_time_sec=0.0)

    def test_completed_runs_are_skipped(self) -> None:
        plan = plan_from_config(BASE_CONFIG)
        done = [self._record_for(p, RunRecorder.__new__(RunRecorder)) for p in plan[:1]]
        # recorder instance unused by start(); use a real one instead
        done = []
        r = RunRecorder(output_dir="unused")
        for p in plan[:1]:
            rec = r.start(config=p.config, seed=p.seed, model_name=p.model_name)
            done.append(RunRecorder.finish(rec, {}, 0.0))
        remaining = resume_filter(plan, done)
        assert [p.seed for p in remaining] == [1, 2]

    def test_config_change_reruns_everything(self) -> None:
        plan = plan_from_config(BASE_CONFIG)
        r = RunRecorder(output_dir="unused")
        done = []
        for p in plan:
            rec = r.start(config=p.config, seed=p.seed, model_name=p.model_name)
            done.append(RunRecorder.finish(rec, {}, 0.0))
        changed = {**BASE_CONFIG, "render": {"width_bucket": 256, "pad_value": 0}}
        assert len(resume_filter(plan_from_config(changed), done)) == 3

    def test_empty_done_returns_full_plan(self) -> None:
        plan = plan_from_config(BASE_CONFIG)
        assert resume_filter(plan, []) == plan
