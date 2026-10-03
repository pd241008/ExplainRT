# Changelog

All notable changes to ByteLens are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added — P0 Scaffold

- Repository layout per AGENTS.md §4: `bytelens/` core library, root-level
  `logger/` and `runner/`, `datasets/`, `models/`, `sandbox/`, `configs/`,
  `tests/`, `paper/`, `notebooks/`.
- Operating brief (`AGENTS.md`) with hard malware-safety and research-integrity rules.
- Strictly pinned `requirements.txt`.
- `bytelens/` domain-module skeleton: `render`, `regions`, `models`, `explain`,
  `attacks`, `defenses`, `eval`.
- `logger/` structured run records (JSONL) with run ID, config hash, git SHA,
  seed, split hash, metrics, wall time, hardware.
- `runner/` config-driven experiment entry point (seed expansion, resume).
- `configs/` experiment templates (one YAML per experiment).
- `sandbox/` Dockerfile and no-network handling protocol (ADR-006).
- Design Dungeons-format ADR catalog: ADR-000 through ADR-007.
- Postmortem registry with template.
- CI workflow: pytest + ruff on every push and PR.

### Fixed

- CI: the install step failed on Python 3.11 because `numpy==2.5.3` and
  `scipy==1.18.1` require Python >= 3.12. Dropped 3.11 from the test matrix
  (now 3.12 only) and bumped `requires-python`, the ruff target, and the
  mypy target to 3.12. Runtime pins are unchanged.

### Decisions

- ADR-000: adopt Design Dungeons conventions; record path corrections.
- ADR-001: canonical flag-based PE region partition.
- ADR-002: shared differentiable resize for train/infer/attack.
- ADR-003: split protocol (random / near-duplicate / time-aware / open-set).
- ADR-004: multi-seed and statistics protocol.
- ADR-005: collapse guard, tolerances, ECT-A (pre-registered).
- ADR-006: safe malware handling and sandbox boundary.
- ADR-007: run records and reproducibility.
