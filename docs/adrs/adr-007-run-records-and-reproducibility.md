# 📜 ADR-007: Run records and reproducibility

> **Status:** `Decided`
> **Date:** October 2026

---

## 🌎 Context

The hard rule "no number enters the paper unless it traces to a run ID,
config, and seed" needs a concrete mechanism: what a run record is, what it
must contain, and how a paper table points back to it. Design Dungeons §13
(ChaosSeal honesty-first policy) provides the pattern: JSON artifacts with
fixed fields, fixed seeds, everything reproducible from committed inputs —
no generated artifacts in git.

The alternative — collecting numbers into spreadsheets or prose — is how
results drift from code, and how untraceable numbers reach drafts.

## 🛤️ Options Considered

1. **Spreadsheet / hand-maintained results table** — flexible; decays
   immediately; untraceable; forbidden by hard rules anyway.
2. **Experiment-tracking SaaS (W&B/MLflow)** — polished; adds an external
   dependency, account, and network requirement to the reproducibility chain;
   overkill for a single-author paper repo.
3. **Local structured records (JSONL) with required identity fields, plus
   scripts that generate paper tables/figures from them** — offline,
   diffable, versioned by git, and directly enforceable by validation code. ✅

---

## 🎯 Decision

> [!IMPORTANT]
> **Every run writes one JSONL record in `logger/` with required fields:
> `run_id`, `created`, `config_hash`, `config`, `git_sha`, `seed`,
> `dataset_split_hash`, `model_name`, `metrics`, `wall_time_sec`,
> `hardware`, `requirements_hash`. Records missing required fields are
> rejected at load. Paper tables and figures are generated from these
> records by scripts in `paper/` — never typed by hand. Missing values are
> `null`, never invented.**

Implemented in this scaffold (`logger/run_records.py`):

- `config_hash`: SHA-256 over the canonical JSON of the config
  (order-insensitive); the config is embedded in the record itself.
- `git_sha`: captured at record creation; `null` outside a repo.
- `requirements_hash`: SHA-256 of the pinned `requirements.txt`, tying a
  record to an environment lock (Design Dungeons §06 spirit).
- `resume_filter` in `runner/` keys on
  `(experiment, model, seed, config_hash)` — reruns are deduplicated by
  identity, and any config change re-runs by design.

Traceability chain for any paper number:
`paper table → generation script → run_id → record → config + git SHA +
seed + split hash`.

## 🧠 Reasoning

JSONL over a service keeps the whole chain inside the repo: it diffs, it
reviews, it survives offline work, and it can be validated by the same
codebase that produces it (a record missing fields cannot even be loaded).
Embedding the full config in each record trades disk space (trivial) for
self-containment: a five-year-old record still explains itself without
archaeology.

## ⚖️ Consequences

- **Good:** 🟢 Untraceable numbers are structurally impossible to cite — the
  chain starts at a validated record or does not exist.
- **Good:** 🟢 Records are plain text: reviewable in PRs, greppable,
  permanent.
- **Bad:** 🔴 A query layer (Parquet/pandas) is needed once records
  accumulate; planned in P1 using already-pinned pyarrow.
- **Bad:** 🔴 Records contain hardware and git context, so they are not
  byte-stable across machines — comparisons are by field, not by file hash.

## 🔄 Revisit When

- Record volume makes JSONL scans slow (P4 full runs) → Parquet export with
  identical schema, JSONL remains the write path.
- A new required field is needed (e.g. attack budget spent) → schema
  migration note in this ADR + reader keeps accepting old records.
- Results sharing with collaborators/reviewers is requested → add an export
  script; the schema stays the contract.
