"""Config validation, seed expansion, run planning, resume (P0 scope).

Design rules enforced here:

- Seeds live in the config file, never in code (AGENTS.md section 2).
- One experiment = one YAML in ``configs/``; the config hash in every
  ``logger/`` record pins the exact setup.
- The runner never invents values: a config missing required keys is an
  error, not a default.

Execution (training loops) lands in P1, wired to ``bytelens.models``;
this module owns the deterministic planning that tests can verify now.
"""

from __future__ import annotations

import copy
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from logger.run_records import RunRecord, config_hash

REQUIRED_KEYS = ("experiment", "model", "seeds")


@dataclass(frozen=True)
class PlannedRun:
    """One (experiment, model, seed) execution unit."""

    experiment: str
    model_name: str
    seed: int
    config: dict[str, Any]

    @property
    def config_hash(self) -> str:
        """Hash of this run's exact config (seed included)."""
        return config_hash(self.config)

    @property
    def identity(self) -> tuple[str, str, int, str]:
        return (self.experiment, self.model_name, self.seed, self.config_hash)


def load_config(path: str | Path) -> dict[str, Any]:
    """Load and validate one experiment YAML.

    Raises:
        ValueError: if the YAML is not a mapping or misses required keys
            (``experiment``, ``model``, ``seeds``).
    """
    with Path(path).open(encoding="utf-8") as f:
        cfg = yaml.safe_load(f)
    validate_config(cfg)
    return cfg


def validate_config(cfg: Any) -> None:
    """Validate required keys and the seed contract; raise ``ValueError`` otherwise."""
    if not isinstance(cfg, dict):
        raise ValueError("config must be a YAML mapping")
    missing = [k for k in REQUIRED_KEYS if k not in cfg]
    if missing:
        raise ValueError(f"config missing required keys: {missing}")
    seeds = cfg["seeds"]
    if not isinstance(seeds, list) or not seeds:
        raise ValueError("config 'seeds' must be a non-empty list of ints")
    if not all(isinstance(s, int) and not isinstance(s, bool) for s in seeds):
        raise ValueError("config 'seeds' must contain only ints (no bools)")


def expand_seeds(cfg: dict[str, Any]) -> list[dict[str, Any]]:
    """One deep copy of the config per seed; identical except for ``seed``.

    Deterministic: preserves the order and duplicates of the seed list.
    """
    validate_config(cfg)
    expanded = []
    for seed in cfg["seeds"]:
        one = copy.deepcopy(cfg)
        one["seed"] = seed
        expanded.append(one)
    return expanded


def plan_from_config(cfg: dict[str, Any]) -> list[PlannedRun]:
    """Expand a config into planned runs, one per seed."""
    validate_config(cfg)
    return [
        PlannedRun(
            experiment=str(cfg["experiment"]),
            model_name=str(cfg["model"]),
            seed=seed,
            config=one,
        )
        for one, seed in zip(expand_seeds(cfg), cfg["seeds"], strict=True)
    ]


def resume_filter(
    planned: list[PlannedRun], done: list[RunRecord]
) -> list[PlannedRun]:
    """Drop planned runs that already have a record with the same identity.

    Identity = (experiment, model_name, seed, config hash). Changing anything
    in the config therefore re-runs every seed — intended, because the old
    records describe a different experiment.
    """
    done_ids = {
        (
            str(r.config.get("experiment")),
            r.model_name,
            r.seed,
            r.config_hash,
        )
        for r in done
    }
    return [p for p in planned if p.identity not in done_ids]


def main(argv: list[str] | None = None) -> int:
    """Dry-run CLI: validate a config and print the planned runs.

    Usage: ``python3 -m runner.experiment configs/<name>.yaml``
    """
    argv = list(sys.argv[1:] if argv is None else argv)
    if len(argv) != 1:
        print("usage: python3 -m runner.experiment <configs/name.yaml>", file=sys.stderr)
        return 2
    try:
        cfg = load_config(argv[0])
        plan = plan_from_config(cfg)
    except (OSError, ValueError) as exc:
        print(f"invalid config: {exc}", file=sys.stderr)
        return 1
    print(f"experiment={cfg['experiment']} model={cfg['model']} planned_runs={len(plan)}")
    for p in plan:
        print(f"  seed={p.seed} config_hash={p.config_hash[:12]}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
