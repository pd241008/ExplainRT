# 📜 ADR-004: Multi-seed and statistics protocol

> **Status:** `Proposed` — becomes `Decided` before the first headline claim
> is computed (must be fixed before P2 results enter write-up).
> **Date:** October 2026

---

## 🌎 Context

Single-seed results in adversarial ML routinely reverse under seed variance —
differences that look like method wins are noise. Two dependencies make this
worse for ByteLens specifically: samples cluster into near-duplicate families
(ADR-003), so iid confidence intervals understate uncertainty, and attack
success rates (RQ4) are proportions whose variance depends on the test-set
composition. The paper needs one statistics protocol fixed **before** results
exist, so that no test can be chosen after seeing outcomes.

## 🛤️ Options Considered

1. **Single seed + mean over test samples** — cheap; indefensible for TIFS.
2. **Multi-seed with iid bootstrap CIs** — better, but wrong under clustered
   data: treats dependent samples as independent and narrows CIs.
3. **Multi-seed + cluster bootstrap + permutation tests** — correct under
   clustering; more compute and a fixed testing plan. ✅

---

## 🎯 Decision

> [!IMPORTANT]
> **Development runs use ≥ 5 seeds; headline claims use 10 seeds (AGENTS.md
> §2). Uncertainty comes from cluster bootstrap over near-duplicate clusters
> (95% CI); method comparisons use paired permutation tests on the same
> splits/seeds with Holm–Bonferroni correction across the comparison family.
> The full testing plan (metrics, contrasts, correction) is written in this
> ADR before headline runs; post-hoc tests are labeled exploratory.**

Protocol details:

- Seeds are integers in the config; the seed list is part of the config hash
  (ADR-007), so a headline claim names its exact seeds.
- Cluster bootstrap: resample clusters (with replacement) to cluster-count,
  compute the statistic per replicate; 10,000 replicates unless config says
  otherwise.
- Permutation tests: paired per (split, seed); sign flips under the null;
  reported with effect sizes, not p-values alone.
- Multiple comparisons: Holm–Bonferroni within each claim family declared
  here: (a) split-protocol gaps per model, (b) defense vs no-defense per
  attack, (c) ECT vs canonicalization vs adversarial training.
- Exploratory analyses are labeled as such in the paper and get no claim
  status.

## 🧠 Reasoning

Clustering breaks iid assumptions for every metric computed over samples, and
seed variance breaks claims computed over single training runs — the protocol
handles both at once. Fixing contrasts and corrections in advance is what
makes "we tested what we planned to test" checkable from the ADR plus run
records, without trusting anyone's memory.

## ⚖️ Consequences

- **Good:** 🟢 Headline numbers carry defensible uncertainty; the paper can
  answer the "is this just seed noise / cluster leakage" review question with
  a pointer here.
- **Good:** 🟢 The declared claim families bound the multiple-comparison
  problem honestly instead of ignoring it.
- **Bad:** 🔴 10 seeds × 4 splits × several models is expensive; mitigated by
  the P2 pilot (5 seeds) deciding what earns headline compute.
- **Bad:** 🔴 Contrast decisions are locked before results; a surprise finding
  needs a protocol amendment (public, in this ADR) rather than a quiet new
  test.

## 🔄 Revisit When

- Pilot variance estimates show 10 seeds are insufficient (or excessive) for
  separability — amend the seed count here before P4, with reasons.
- A reviewer-anticipated analysis (e.g. Bayesian hierarchical model) is added
  — extend, don't replace; original claims keep their original protocol.
