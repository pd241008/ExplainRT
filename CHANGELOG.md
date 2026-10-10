# Changelog

All notable changes to ByteLens are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added — Track A: BODMAS feature pipeline (ADR-010)

- **ADR-010**: Track A (BODMAS feature pipeline) — interim npz-only mode and
  full-data mode clearly separated, loader contract, split builders, subset
  sampling, metric definitions, and the baseline plan fixed **before** any
  real run.
- `bytelens/data/bodmas.py`: loader with `allow_pickle=False`, metadata
  joined by row order (matching the existing raw-file test's layout), family
  by sha256, shape/finiteness/label-agreement assertions, and
  `mint_npz_row_id` for interim identities.
- `bytelens/eval/splits.py`: random (stratified 70/15/15), time-aware (train
  < val < test by first-seen month), open-set (families held out by
  first-seen date), and near-duplicate-proxy (seeded cosine-LSH buckets,
  cluster-disjoint sides) — each returning ID lists plus a
  `splits.lock.json` entry via `logger.splits`; interim npz-only splits
  require the `_npzonly` suffix.
- `bytelens/eval/subsets.py`: 10% pilot subset, stratified by label and
  feature bucket within month, fixed seed, minimum-stratum guard.
- `bytelens/eval/metrics.py`: macro-F1, per-family recall, and AUT as
  pre-registered in ADR-010 (monthly windows; present families only).
- `bytelens/models/lightgbm_baseline.py`: config-driven LightGBM baseline
  (seed and hyperparameters come from the YAML, never defaults in code),
  v2-compatible artifact digest; sanity tests cover shuffled-labels
  near-chance and random > time-aware on synthetic drift.

### Added — Dataset roles & preliminary run (ADR-008 rev 2)

- **ADR-008 rev 2**: dataset roles, controlled combination, and BODMAS
  fallback — three named training regimes (R1 single-source, R2
  leave-one-dataset-out, R3 pooled with per-dataset locked test windows);
  combination rules (cross-dataset dedup before splitting, v2-feature pooling
  only, label alias table, class-source confound guard, source share caps,
  TRITIUM/INFERNO test-only by default, disarm-field normalization), shortcut
  audit **S8** (source predictable ⇒ cross-source claims invalid), EMBER2024
  (v3 features) as a separate track, and the image/PE-edit binary fallback
  (RawMal-TF, MalwareBazaar, MOTIF, month-stratified SOREL subset).
- `configs/p1_prelim_r1_bodmas.yaml`: preliminary run under regime R1 on the
  only ingested v2 source (BODMAS features), time-aware split protocol, 5 dev
  seeds, tagged `smoke`/`prelim`/`R1` so table generators refuse it.
- `scripts/run_prelim.py`: preliminary-run executor (manifest verification
  → plan → deterministic pipeline → chained run records with resume).
- Preliminary-run records appended to `logger/runs.jsonl` (run_ids
  `95b233a4990e`, `d14b7d502117`, `ee446c3333f5`, `a9e2bb190ad5`,
  `20eaac7e55ef`; dataset_hash `d2d07b424c66…`); `python -m logger.repro`
  PASSES with an exact metric match on each seed. Reference-pipeline metrics
  only — no model-training numbers until P1.

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
