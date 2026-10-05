# Changelog

All notable changes to ByteLens are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added — Provenance & Traceability (ADR-009)

- **ADR-009**: provenance, hashing, and result traceability — custom JSONL
  hash chain chosen over MLflow/DVC (alternatives recorded in the ADR).
- `logger/hashing.py`: canonical SHA-256 hashing — `canonical_json` (sorted
  keys, stable float formatting), `hash_file` (streamed), `hash_array`
  (dtype+shape bound), `hash_config` (order-insensitive), `hash_split_ids`.
- `datasets/MANIFEST.json` (tracked, metadata only) + `logger/manifest.py`:
  per-raw-file entries (source, retrieval date, size, sha256, license note,
  npz structure), `dataset_hash`, path-safety (no absolute/traversal paths),
  and the `python -m logger.manifest verify` (verify-data) command that fails
  loudly on any mismatch. Raw files are only ever read.
- `logger/splits.py`: sample IDs are sha256s; split side files
  (`datasets/splits/<name>/<split>.txt`, sorted) plus `splits.lock.json`
  recording counts, per-side and whole-split hashes, and the split spec
  (algorithm version, seed, windows, sampling fraction, dataset hash).
- Run records v2 (schema_version 2): **derived run IDs**
  (`sha256(config_hash|dataset_hash|split_hash|git_sha|seed)[:12]`), full
  resolved config, git dirty flag + diff hash, branch, environment (Python,
  frameworks, CUDA, requirements hash, sandbox image), all seeds +
  determinism flags, `tags`, `test_touched` + `test_lock_hash`, model
  artifact sha256, and a **tamper-evident hash chain**
  (`prev_record_hash`/`record_hash`). ADR-007 (v1) records remain readable.
- `runner/locks.py`: `freeze` writes `configs/frozen/<name>.lock`
  (config/split/dataset hashes, git SHA, date); evaluating a locked test
  window without a matching lock is refused; `final`-tagged runs require a
  clean git tree and a matching lock.
- `runner/execution.py`: deterministic seeded reference pipeline so
  reproducibility is provable ahead of P1 training loops.
- `paper/tables.py`: table artifacts (`paper/artifacts/<id>.json` +
  `paper/build_manifest.json`) recording run_ids, all hashes, generator git
  SHA, and output sha256; generators **refuse** `smoke`/`pilot-10pct` runs
  and any `test_touched` run without a matching lock.
- CLIs: `python -m logger.trace <artifact-id | run_id>` (full chain +
  reproduction command), `python -m logger.verify` (recompute data, split,
  and record-chain hashes; loud failures), `python -m logger.repro <run_id>`
  (re-run with recorded config/seed; exact or tolerance-compared metrics,
  tolerance stated).

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
- ADR-009: provenance, hashing, and result traceability (JSONL hash chain,
  pre-registration locks, paper-side refusal rules).
