# ADR-009: Provenance, hashing, and result traceability

- **Status:** Decided
- **Date:** 2026-10-05
- **Refines:** ADR-007 (run records) — extends the record identity with the full
  data / split / code / environment chain, adds tamper evidence and
  pre-registration locks, and makes paper-side refusal rules executable.

## Context

ADR-007 gives every run a JSONL record, and AGENTS.md §2 makes it a hard rule
that no number enters the paper without a run ID, config, and seed. Identity
fields alone do not close the chain, though:

- "Same config" is only as strong as the canonical form the hash covers.
- Nothing binds a run to the **exact dataset files** it consumed, so a silently
  re-exported dataset invalidates comparisons invisibly.
- The pre-registration rule ("never tune on test windows") has no mechanism —
  nothing *blocks* a run that touches a locked test window.
- Nothing detects an edited or deleted record after the fact.
- Table scripts can pick up smoke/pilot runs by accident; nothing refuses them.

The goal: any paper number resolves, by one command, to the exact data files,
sample set and split, config, code, environment, and seed — and re-running the
chain reproduces the number.

## Options considered

1. **Experiment tracker (MLflow / W&B).** Rich UI and lineage, but adds a
   service, an account, and a network dependency to the reproducibility chain;
   the provenance (JSON artifacts) would live outside git, unreviewable in PRs.
   Overkill for a single-author offline repo. Rejected.
2. **DVC for data + pipeline versioning.** Content-addresses datasets well, but
   the .dvc cache and remotes duplicate what SHA-256 manifests already give us;
   pipeline stage tracking covers a workflow shape we do not have (one config →
   one run). Adds a heavy dependency to a stdlib-sized problem. Revisit if
   multi-GB dataset storage versioning becomes a real need. Rejected for now.
3. **Custom JSONL hash chain (stdlib SHA-256 only).** Each record hashes the
   previous one (`prev_record_hash` → `record_hash`), every input domain gets a
   canonical hash (file bytes, arrays, configs, splits), and locks enforce
   pre-registration. Diffable, reviewable, offline, no new dependencies. ✅

## Decision

> [!IMPORTANT]
> **Every input domain gets a canonical SHA-256 (file bytes, arrays with dtype
> + shape, resolved configs, sorted split ID lists, manifests). Run IDs are
> derived, not sampled: `run_id = sha256(config_hash | dataset_hash |
> split_hash | git_sha | seed)[:12]`. Records are chained
> (`prev_record_hash`/`record_hash`) for tamper evidence. Locked test windows
> are evaluable only under a `freeze` lock with matching hashes; `final` runs
> require a clean git tree and a matching lock; table generators refuse
> `smoke`/`pilot-10pct` runs and unmatched `test_touched` runs. All hashes are
> SHA-256; canonical form is UTF-8 JSON, sorted keys, no whitespace, stable
> float formatting.**

Components (all stdlib + already-pinned packages):

1. **Hashing (`logger/hashing.py`)** — `canonical_json` (sorted keys, UTF-8,
   no extra whitespace, stable float repr), `hash_file` (streamed, chunked),
   `hash_array` (dtype + shape + little-endian raw bytes folded into the hash),
   `hash_config` (hash over the resolved config — YAML resolved to defaults,
   no comments; two key orders hash equal, any value change hashes different).
2. **Dataset manifest (`datasets/MANIFEST.json`, tracked, no data)** — one
   entry per raw file: logical name, source URL, retrieval date, size,
   sha256, license/terms note; for BODMAS features: npz keys, shapes, dtypes,
   label meaning, and the verified row→sha256 mapping check. The
   `dataset_hash` a run records is the hash of the canonical manifest entries
   it uses. `verify-data` recomputes hashes against the manifest and fails
   loudly on mismatch; raw files are never modified.
3. **Sample IDs and splits (`logger/splits.py`)** — the canonical sample ID is
   the sample's sha256 (BODMAS sha). `datasets/splits/<name>/<split>.txt`
   holds sorted IDs; `splits.lock.json` records per split: sample count,
   `split_hash` (hash of the sorted ID list), and the split spec (algorithm
   version, seed, window boundaries, sampling fraction, `dataset_hash`).
   The 10% subsets are stratified by month and family and defined only by a
   frozen ID list plus seed. Never log paths or file contents.
4. **Run records v2 (`logger/run_records.py`)** — keeps the ADR-007 required
   fields and adds `schema_version`, derived `run_id`, full resolved config,
   `git_sha`/`git_dirty` (+ `git_diff_hash` when dirty), branch, environment
   (Python, frameworks, CUDA, hardware, `requirements_hash`, sandbox image
   digest when relevant), all seeds + determinism flags, `tags`
   (`smoke`/`pilot-10pct`/`final`), `test_touched`, model artifact sha256,
   and the chain fields. Append-only: writers never rewrite history.
5. **Freeze/lock (`runner/locks.py`)** — `freeze` writes
   `configs/frozen/<name>.lock` (config_hash, split_hash, dataset_hash,
   git_sha, date). Evaluating on locked test windows requires a lock matching
   the run's hashes; the runner refuses otherwise. `final` runs additionally
   require a clean git tree.
6. **Execution (`runner/execution.py`)** — a minimal deterministic reference
   pipeline (seeded NumPy summary statistics over a provided array) with a
   determinism flag record, so `repro` can prove seed-reproducibility now,
   ahead of P1 training loops.
7. **Paper traceability (`paper/tables.py`)** — generators read only run
   records and emit `paper/artifacts/<id>.json` (run_ids, hashes, generator
   git SHA, output sha256) plus `paper/build_manifest.json`. They refuse
   `smoke`/`pilot-10pct` runs and any `test_touched` run without a matching
   lock.
8. **CLIs** — `python -m logger.trace <artifact-id or run_id>` (print the full
   chain + reproduction command), `python -m logger.verify` (recompute data,
   split, config, and record-chain hashes; report mismatches),
   `python -m logger.repro <run_id>` (re-run with recorded config and seed;
   compare metrics exact for deterministic ops, tolerance otherwise, stated).

## Reasoning

A hash chain plus derived IDs costs ~200 lines of stdlib and makes tampering
*detectable* rather than merely discouraged, which is the difference between
"we promise numbers are real" and "the repo proves it". Keeping the chain in
JSONL inside the repo preserves ADR-007's reviewability (records diff in PRs)
and keeps the whole provenance story offline. Locks turn the pre-registration
hard rule from prose into a gate the runner and the paper generators both
enforce, so "tuned on test" becomes a crash, not a review catch.

## Consequences

- **Good:** 🟢 One command (`logger.trace`) resolves any paper number to data,
  split, config, code, env, and seed — and `logger.repro` re-executes it.
- **Good:** 🟢 Tampering with records, data, or splits is detectable
  (`logger.verify`, `verify-data`); the chain also proves completeness
  (deletions break the chain).
- **Good:** 🟢 Test-window discipline is enforced mechanically at three points
  (runner, locks, paper generator).
- **Bad:** 🔴 `git_sha` in run IDs means uncommitted work changes identity —
  mitigated by the freeze flow (`final` requires a clean tree anyway).
- **Bad:** 🔴 Hash-chain maintenance is manual (a `--repair` escape hatch
  exists but writes a note into the file); chains must be verified before any
  paper build (`logger.verify`).
- **Bad:** 🔴 Records are longer (full config, env, hashes); trivially fine at
  paper scale, becomes a Parquet export question again at sweep scale (ADR-007
  already anticipates this).
- **Neutral:** ⚪ ADR-007's `run_id` format (timestamp + uuid) remains valid
  for records written before this ADR; the chain tolerates mixed formats, and
  new records all use derived IDs.

## Revisit When

- Datasets reach multi-GB scale or need remote storage → adopt DVC alongside
  this scheme (the manifest stays the source of truth; DVC adds transport).
- Collaboration or reviewer access demands a queryable tracker → export the
  same records to MLflow; JSONL remains the write path.
- Records grow past JSONL-scan speed (P4) → Parquet export per ADR-007.
- A provenance domain is added (e.g. adversarial-file lineage) → extend the
  record schema here before first use, with a schema_version bump.
