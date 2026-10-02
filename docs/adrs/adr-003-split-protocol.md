# 📜 ADR-003: Split protocol — random, near-duplicate, time-aware, open-set

> **Status:** `Proposed` — becomes `Decided` before the first P1 split is
> built; requires BODMAS timestamp coverage and family labels confirmed on
> access (AGENTS.md §9 stop-and-ask).
> **Date:** October 2026

---

## 🌎 Context

RQ1 asks how much of the reported performance of image-based malware
classifiers is evaluation bias. Malware datasets duplicate heavily (packed
variants, recompiled families), and threats evolve over time, so three
failure classes dominate reported numbers:

1. **Near-duplicate leakage** — near-identical samples on both sides of a
   random split; the model memorizes the cluster, accuracy inflates.
2. **Temporal leakage** — training on the future; deployment-time drift is
   invisible in the evaluation.
3. **Closed-set assumption** — test families all appear in training; the
   open-set reality (novel families) is never measured.

BODMAS provides family labels and timestamps, enabling all four protocols.
Split files are the only dataset artifact tracked in git (hash lists only,
AGENTS.md §4).

## 🛤️ Options Considered

1. **Random split only** — comparable to legacy papers; maximally optimistic;
   kept as the *bias reference*, not the headline.
2. **Three leakage-controlled protocols (near-dup, time-aware, open-set) +
   random baseline** — measures the bias RQ1 asks about. ✅
3. **Custom k-fold scheme** — more variance estimates, but none of the folds
   map to a deployment question; weakens the RQ1 story.

---

## 🎯 Decision

> [!IMPORTANT]
> **Every model/defense/attack comparison runs under four splits: `random`,
> `near_duplicate`, `time_aware`, `open_set`. Clusters are formed on
> near-duplicate detection over parsed features and never cross splits;
> time-aware windows enforce train dates < validation dates < test dates;
> open-set holds whole families out of training. Splits are tracked as JSON
> hash lists with protocol version, config hash, and seed.**

Protocol details:

- **random**: stratified 70/15/15 by family, seeded; the bias baseline.
- **near_duplicate**: clustering (exact-hash plus near-duplicate threshold
  fixed in config) over PE metadata/features; whole clusters go to one side.
  70/15/15 at cluster level.
- **time_aware**: order by timestamp; earliest 70% train, next 15% validation,
  latest 15% test. Strict date ordering, no overlap.
- **open_set**: 20% of test-only families (seeded, config-fixed) never appear
  in train/val; evaluation reports both closed- and open-set metrics.

Leakage invariants (tested in `tests/unit/test_splits.py`, P1): no cluster
crosses splits; date ordering holds; fixed seed + same input ⇒ identical
split; AUT handles absent families.

## 🧠 Reasoning

RQ1 requires the random baseline to quantify the gap the other protocols
close. Holding the protocols in one ADR keeps them versioned together: a
paper claim about evaluation bias is a claim about the *set* of protocols.
Config-fixed seeds and thresholds make every split reproducible from the
config hash alone.

## ⚖️ Consequences

- **Good:** 🟢 The RQ1 headline (bias gap) is directly computable; leakage
  invariants are testable properties, not review promises.
- **Good:** 🟢 Split files double as the open-set family-selection record —
  auditable, no undocumented exclusions.
- **Bad:** 🔴 Four splits quadruple compute for every comparison; budgeted by
  running P1 baselines on all four but attack/defense sweeps only where the
  pilot justifies it.
- **Bad:** 🔴 Near-duplicate thresholds and the open-set family fraction
  become pre-registered choices — they must be ADR-fixed before the split is
  built, not after seeing results.

## 🔄 Revisit When

- BODMAS timestamp/family coverage turns out partial (protocol falls back to
  what the data supports; this ADR is amended before P1 uses it).
- A deduplication method change (e.g. different clustering) is proposed — new
  ADR, both protocols reported for continuity.
- The paper adds a second dataset in supplement scope (protocol ports get
  their own ADR).
