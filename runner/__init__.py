"""Config-driven experiment runner (root-level, first-class — Design Dungeons).

The unit of reproducibility is one YAML file in ``configs/`` (AGENTS.md
section 4). The runner validates a config, expands the seed list (seeds are
fixed in config, never in code — hard rule, AGENTS.md section 2), and turns
each (config, seed) pair into a planned run that executes through
``bytelens`` models and writes a ``logger/`` record per run.

Resume support: runs whose identity (experiment, model, seed, config hash)
already has a record are skipped, so interrupted sweeps continue where they
stopped. Execution wiring lands in P1; planning and resume are ready now.
"""

from __future__ import annotations

from runner.experiment import PlannedRun, expand_seeds, load_config, plan_from_config, resume_filter

__all__ = [
    "PlannedRun",
    "expand_seeds",
    "load_config",
    "plan_from_config",
    "resume_filter",
]
