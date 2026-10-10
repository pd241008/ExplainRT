# 📜 ADR-010: Track A — BODMAS feature pipeline (loader, splits, metrics, LightGBM)

> **Status:** `Proposed` — becomes `Decided` when the first split is frozen
> (`python -m runner.locks freeze`); blocked decisions are called out below.
> **Date:** 2026-10-09
> **Implements:** ADR-003 (split protocol, §"P1" details), ADR-008 rev 2 (R1,
> BODMAS features), ADR-009 (provenance). Per AGENTS.md: small PRs, tests on
> synthetic data only, no pilot on test windows, `pilot-10pct` tag, never
> invent numbers.

---

## 🌎 Context

Track A delivers the first real results in the repo: LightGBM over the
BODMAS feature release (EMBER v2, 2381 features, 134,435 rows) under the
RQ1 split comparison (random / near-duplicate-proxy / time-aware / open-set),
plus the 10% pilot subset and AUT. Two constraints shape implementation:

1. **Metadata files are missing.** `datasets/MANIFEST.json` tracks
   `bodmas_metadata.csv` (sha256, timestamp) and
   `bodmas_malware_category.csv` (family, joined by sha256), but neither file
   is present in `datasets/raw/` today. Only `bodmas.npz` verifies
   (`python -m logger.manifest verify bodmas_features` → OK). Decision
   (per user, 2026-10-09): build the loader with an **interim npz-only
   mode** — features and labels are loadable; sha256 row IDs, timestamps
   and families are deferred until the CSVs arrive.
2. **No paper spec exists yet** (`paper/malware_tifs_paper.tex` is absent),
   so the AUT definition must be fixed here before any AUT number is
   computed.

The missing columns block: `sha256`-keyed split lists (the npz has no sha
column — row order is the only link to the missing metadata), the
time-aware split (needs first-seen timestamps), open-set (needs families),
and AUT over monthly windows (needs both). The interim mode makes that
visible in every generated identity so no interim hash is mistaken for a
final one: split IDs in interim mode are sha256 strings minted from
`sha256("npz_row" | row_index | npz_file_sha256)[:64]`, the lock entry
records `id_basis: "row_index"`, and split names carry an `_npzonly`
suffix. Because the npz file hash is fixed in the manifest, the same npz
always yields the same minted IDs, and when the CSVs arrive (same row
order) every interim split converts line-for-line to real sha256 IDs.

Related: `bytelens/eval/` and `bytelens/models/` currently raise
`NotImplementedError` (P1 stubs); `runner/execution.py` is the seed-only
reference pipeline. Track A replaces the compute step for the LightGBM
model only; every other model stays stubbed.

## 🛤️ Options Considered

1. **Block all Track A coding on the CSVs** — safest identity-wise, but kills
   a full code layer that can be built and tested now on synthetic data.
2. **npz-only interim mode (chosen)** — loader takes paths, optional
   metadata; split/metrics models are fully separable from that difference,
   so interim runs are gated behind the `smoke` tag and never reach
   tables (`paper/tables.py` already refuses `smoke`).
3. **Derive sha from feature bytes** — rejected: hashing feature vectors as
   a "sha" breaks the provenance chain (ADR-009) — the sha of a sample is
   the sha256 of the PE file bytes, not of its representation.

---

## 🎯 Decision

> [!IMPORTANT]
> **1. Loader (`bytelens/data/bodmas.py`).** Load X, y from the npz with
> `allow_pickle=False`; metadata and category CSVs are optional and joined
> **by row order** (metadata) and **by sha256** (category), with the label /
> family-presence agreement asserted on every row. Rejects wrong shapes
> (134,435 × 2,381), anything beyond {0,1} in y, non-finite X. Interim
> npz-only mode: metadata absent ⇒ no sha/timestamps/families; interim runs
> set `data_mode: npz_only` in the config and carry the `smoke` tag.

> [!IMPORTANT]
> **2. Splits (`bytelens/eval/splits.py`).** Protocols per ADR-003, each
> writing side files through `logger.splits.write_split_ids` and a
> `splits.lock.json` entry through `make_lock_entry`:
> - **random**: stratified 70/15/15 by label (interim) / family (final),
>   seeded from config.
> - **time-aware**: train < validation < test by first-seen month. Requires
>   timestamps — the builder raises in interim mode rather than faking
>   months.
> - **open-set**: hold out whole families (by first-seen date for family
>   selection). Requires families — raises in interim mode.
> - **near-duplicate-proxy**: cluster on the feature matrix (hash-based
>   bucketing of L2-normalized rows; exact-hash buckets first, then
>   cosine-radius clusters), assign each cluster to exactly one side,
>   70/15/15 at cluster level. Available in both modes (needs only X); NOT
>   a substitute for the PE-hash near-duplicate protocol of ADR-003.
>
> Source IDs: final splits use the `sha` column of the metadata CSV; interim
> splits use minted row IDs (`sha256("npz_row"|i|npz_sha)[:64]`) and record
> `id_basis: "row_index"` plus the `_npzonly` name suffix.

> [!IMPORTANT]
> **3. 10% pilot subset.** Sample within every (month, family) stratum —
> interim mode: (label, feature-hash bucket) stratum — fixed seed from
> config, minimum stratum size fixed **here, before any pilot split is
> generated**: **min_stratum = 50** (a stratum smaller than 50 contributes
> proportionally but is recorded in the lock entry's `stratification`
> field; no stratum is silently dropped). The surviving-strata list is
> written into the split lock entry. Pilot runs carry the `pilot-10pct` tag
> (refused by `paper/tables.py`).

> [!IMPORTANT]
> **4. Metrics (`bytelens/eval/metrics.py`).** Macro-F1, per-family recall,
> and **AUT**, defined as follows (Pendlebury-style, adapted to monthly
> windows where BODMAS covers Aug 2019 – Sep 2020):
> - Sort test samples by timestamp into consecutive **windows** = calendar
>   months (a window with zero test samples for a given family = that
>   family is **absent in that window**).
> - For each window w and family f: recall_f(w) over the samples of f inside
>   w if f is present, else **`None`**.
> - Window score(w) = macro-average over **present** families only; a
>   window with zero present families yields `None`.
> - **AUT = mean of the series of per-window scores over the windows where a
>   score exists**, i.e. it never averages `None` as a number and never
>   re-weights a window by its size. Per-family AUT = same reduction reduced
>   over windows for one family (absent months skipped).
> - Per-family recall that a model never produces for an absent family is
>   defined as **0.0** **only at the closed-set / open-set reporting edge**;
>   AUT itself never substitutes a zero for a missing window.
> - Interim mode: AUT is **not computed** (no timestamps); interim metrics
>   are macro-F1 and per-side label-based only.

> [!IMPORTANT]
> **5. LightGBM baseline (`bytelens/models/lightgbm_baseline.py`).**
> Config-driven: all hyperparameters, seeds, and the split name come from
> the YAML file; seeds never default in code. After training, writes a
> **schema-version-2 run record** carrying `split_name`, `dataset_hash`
> (from `logger.manifest.dataset_hash`), `dataset_split_hash` (split hash
> from `logger.splits`), and `model_artifact_sha256`. The record keeps
> sequence `test_touched=True` when evaluating a test set only after a
> matching `configs/frozen/*.lock` exists (`runner.locks.check_lock`).
> **pilot-10pct runs carry the `pilot-10pct` tag** and are refused by
> `paper/tables.py` by construction.

> [!IMPORTANT]
> **6. Sanity tests, run on synthetic data only (AGENTS.md §7).**
> - Shuffled labels yield macro-F1 near chance (≤ ~0.55 for two classes
>   with a margin), recorded as an assertion in
>   `tests/unit/test_lightgbm_baseline.py`.
> - On synthetic drift data (label-dependent feature mean shifts by month),
>   random-split macro-F1 > time-aware macro-F1* — the RQ1 gap exists on
>   data we control.
> - Every edit to split files changes the lock hash (already tested in
>   `tests/unit/test_splits.py` — logger-side).

> ---

## ⚖️ Consequences

- **Good:** 🟢 Track A code and tests exist before the metadata files do, so
  once the CSVs arrive, only a metadata join enables real splits.
- **Good:** 🟢 Every run record carries dataset hash, split hash, and model
  hash; the LightGBM baseline is byte-traceable without touching
  `paper/tables.py`.
- **Good:** 🟢 AUT is defined before any AUT number exists, so it cannot be
  chosen after seeing results.
- **Bad:** 🔴 **Interim results carry no provenance meaning**: real splits
  (time-aware, open-set) are impossible until the CSVs exist; recorded
  interim numbers are blocked at tables and must be labeled `smoke` in
  `CHANGELOG.md` notes (no interim number may be quoted as RQ1 evidence).
- **Bad:** 🔴 Near-duplicate-proxy on raw EMBER features (L2-normalized)
  forms *some* clusters, but a real near-duplicate split needs PE-level
  hashes; the proxy is explicitly NOT the paper's near-duplicate protocol
  and is reported with that caveat, never as its substitute.
- **Bad:** 🔴 AUT's monthly reduction is a methodological commitment: if the
  paper later defines AUT differently (e.g., weekly windows or
  cumulative-training windows), ADR-010 gets a revision and all interim plan
  code must be re-run — cheaper than silently changing definitions.

## 🔄 Revisit When

- The CSVs arrive (metadata join, real sha-keyed splits, AUT activation).
- BODMAS timestamps turn out to require a preprocessing (unit mismatch,
  out-of-range) — loader-side, documented, before the first time-aware split.
- The paper's AUT definition differs from the one fixed here — ADR-010 rev 2
  before any AUT enters the write-up (AGENTS.md §9: stop and ask).
