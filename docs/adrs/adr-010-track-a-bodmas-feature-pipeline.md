# 📜 ADR-010: Track A — BODMAS feature pipeline (loader, splits, metrics, LightGBM)

> **Status:** `Proposed` (rev 2, 2026-10-10: AUT set to the paper's
> trapezoid-over-windows macro-F1 definition; `near-duplicate` split renamed
> to `near_duplicate_proxy` everywhere with an explicit RQ1-validity note) —
> becomes `Decided` when the first split is frozen
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
> - **near_duplicate_proxy** (renamed from `near-duplicate`, ADR-010 rev 2):
>   cluster on the feature matrix (hash-based bucketing of L2-normalized
>   rows; exact-hash buckets first, then cosine-radius clusters), assign
>   each cluster to exactly one side, 70/15/15 at cluster level. Available
>   in both modes (needs only X).
>   **⚠ RQ1-invalidity note (rev 2):** this split is NOT a valid measurement
>   instrument for RQ1 (evaluation bias) claims. The near-duplicate buffer
>   of ADR-003 exists to prevent near-duplicate samples from straddling
>   train/test and thus overstating scores; this proxy clusters raw EMBER
>   feature vectors (LSH over normalized rows), not PE content, so it does
>   not model the same duplicate structure. Comparing `_proxy` scores to
>   random-split scores therefore characterizes feature-space cluster
>   leakage only — in pilot/smoke reporting it must be labeled
>   `near_duplicate_proxy`, never `near-duplicate`, and it must never be
>   quoted as the paper's near-duplicate result. The RQ1-valid split lands
>   when PE-file hashes make the exact-hash buffer of ADR-003 possible.
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
> and **AUT**. **Rev 2: AUT follows the paper's definition** (supersedes the
> interim recall-based definition of rev 1, which was fixed in the absence
> of the paper spec — flagged then in Revisit When): a trapezoidal
> integration over windows of the **macro-F1** in each window, averaged
> over **families present in both train and the window**:
> - Sort windows chronologically by first-seen timestamp (calendar months
>   for BODMAS Aug 2019 – Sep 2020).
> - For each family f and window w in f's active window range: a family is
>   **eligible** for (f, w) iff f has training samples **and** f has ≥1
>   sample in window w. Absent-in-train families are excluded entirely
>   (they are the open-set axis, reported separately, never inside AUT).
> - Window-family score = macro-F1 over the samples of the eligible
>   families in w (computed with `macro_f1` from §4, not per-family recall).
> - **AUT = trapezoidal integral of window macro-F1 over t (window index)
>   normalized by the number of windows−1** — i.e.
>   `AUT = Σ ½(s_i + s_{i+1})·Δt_i / Σ Δt_i` over consecutive windows with
>   scores, so linearly-interpolated area equals the mean under uniform
>   spikes but re-weights genuinely missing/sampled months.
> - **Family granularity:** AUT is computed per family (one curve each) and
>   the headline AUT is the unweighted mean over eligible families' AUTs —
>   the paper's per-family AUT table and the headline number therefore
>   come from the same series.
> - Interim npz-only mode: AUT is **not computed** (no timestamps/families);
>   interim metrics are macro-F1 and per-side label metrics only, and the
>   record stores `aut: null`.
> - **Drift guard (rev 2):** `tests/unit/test_metrics.py` pins the formula
>   with hand-computed trapezoid values on synthetic windows: a test fails
>   if the formula drifts (e.g. someone reintroduces plain-mean or
>   recall-based scoring).

> [!IMPORTANT]
> **5. LightGBM baseline (`bytelens/models/lightgbm_baseline.py`) wired
> through `runner/pilot.py` (rev 2).** Config-driven: all hyperparameters,
> seeds, and the split name come from the YAML file; seeds never default in
> code. After training, writes a **schema-version-2 run record** carrying
> `split_name`, `dataset_hash` (from `logger.manifest.dataset_hash`),
> `dataset_split_hash`, and `model_artifact_sha256`. **Pilot execution
> path (rev 2):** `runner/pilot.py` loads the BODMAS npz, samples the 10%
> subset (`bytelens.eval.subsets`, label-stratified in npz-only mode; the
> feature-bucket strata blow up to ≥1-per-bucket and are NOT used for
> sampling), builds the split **inside the subset** (random or
> `near_duplicate_proxy`; time-aware/open-set raise in npz-only mode),
> trains on the train side, and evaluates **on the validation side only**
> (`test_touched=False`; the test side is never scored before a freeze
> lock exists). Metrics: `val/macro_f1`, `val/n`, and `val/aut` — which is
> **null** in npz-only mode (no timestamps/families; ADR-010 §4 rev 2
> definition activates with the CSVs). Compiler entry:
> `python -m scripts.run_prelim` (delegates to `runner.pilot.main`),
> resumable via the (experiment, model, seed, config_hash) identity in
> `logger/runs.jsonl`. **Pilot runs carry the `pilot-10pct` tag** and are
> refused by `paper/tables.py` by construction.

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
- **Good:** 🟢 AUT is defined before any AUT number exists (rev 1 in the
  absence of the paper; **rev 2 aligns it with the paper's
  trapezoid-over-windows macro-F1 definition**), so it cannot be chosen
  after seeing results.
- **Bad:** 🔴 **Interim results carry no provenance meaning**: real splits
  (time-aware, open-set) are impossible until the CSVs exist; recorded
  interim numbers are blocked at tables and must be labeled `smoke` in
  `CHANGELOG.md` notes (no interim number may be quoted as RQ1 evidence).
- **Bad:** 🔴 Near-duplicate-proxy on raw EMBER features (L2-normalized)
  forms *some* clusters, but a real near-duplicate split needs PE-level
  hashes; the proxy is explicitly NOT the paper's near-duplicate protocol
  and is reported with that caveat, never as its substitute.
- **Bad:** 🔴 AUT's monthly reduction is a methodological commitment:
  ADR-010 rev 2 embeds the paper's trapezoid-over-windows macro-F1
  definition; if the paper's actual `malware_tifs_paper.tex` disagrees with
  the implementation on any metric, this is the "stop and ask" trigger
  (runs halt; the metric does not silently get redefined).

## 🔄 Revisit When

- The CSVs arrive (metadata join, real sha-keyed splits, AUT activation).
- BODMAS timestamps turn out to require a preprocessing (unit mismatch,
  out-of-range) — loader-side, documented, before the first time-aware split.
- The paper's `malware_tifs_paper.tex` becomes available and its AUT text
  (or any metric wording) disagrees with this ADR — code halts, ask a human
  (AGENTS.md §9), never patch silently.
