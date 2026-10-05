<div align="center">

# ExplainRT 🔬

**PE-valid problem-space attacks that fool both the predictions *and* the
Grad-CAM explanations of image-based malware classifiers — and an
Explanation-Consistency Training (ECT) defense with a pre-registered collapse
guard.**

[![Python](https://img.shields.io/badge/python-3.12%2B-3670A0?style=flat-square&logo=python&logoColor=white)](https://python.org)
[![Status: Research](https://img.shields.io/badge/status-research-purple?style=flat-square)](README.md#-phases)
[![CI](https://github.com/pd241008/ExplainRT/actions/workflows/ci.yml/badge.svg)](https://github.com/pd241008/ExplainRT/actions/workflows/ci.yml)

</div>

---

## 📖 Abstract

Reported robustness of image-based malware classifiers is inflated by three
quiet failures: near-duplicate leakage across random splits, shortcut features
that survive on benchmark data but not in deployment, and explanations that
look plausible without being faithful. ExplainRT measures all three first —
random vs near-duplicate vs time-aware vs open-set splits, shortcut audits,
and Grad-CAM sanity/faithfulness checks. It then attacks **both predictions
and explanations** with PE-valid, budget-constrained file edits that keep
samples parseable and executable-code intact (A1–A8, including an adaptive
attack against every defense), and defends with ECT against input
canonicalization and adversarial training under an equal tuning budget.
Every number in the paper traces to a run record — config hash, git SHA,
seed, split hash — or it does not exist.

> **Status: P0 scaffold complete** — layout, CI, sandbox boundary, ADR-000…007,
> logger, and runner planning. P1 (data + baselines) waits on BODMAS access
> and the paper source, both stop-and-ask items. No results exist yet, by
> design (see [Results](#-results)).

---

## 🧪 Results

> [!IMPORTANT]
> **Honesty-first policy (AGENTS.md §2):** every cell below is populated only
> from `logger/` run records (run ID, config, seed) by scripts in `paper/` —
> never typed by hand, never estimated. The table is the schema; the numbers
> land with P4 (10 seeds) after the week-6 venue gate.

| Attack / Metric | Baseline | This Work | Notes |
| --------------- | -------- | --------- | ----- |
| Random-split accuracy | — | — | bias reference (ADR-003) |
| Near-duplicate-split accuracy | — | — | RQ1 leakage gap |
| Time-aware accuracy / AUT | — | — | RQ1 temporal drift |
| Grad-CAM faithfulness | — | — | RQ3, post-audit S1–S4 |
| A1 / A3 / A4 / A6 success | — | — | RQ4, budget-limited |
| A8 (adaptive) vs ECT / D1 / D2 | — | — | no claim without A8 |
| Clean-accuracy cost of defense | — | — | collapse-guard verdict (ADR-005) |

---

## ⚡ Quickstart

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt -r requirements-dev.txt

pytest                     # unit tests — offline, synthetic PEs only
ruff check .               # lint (CI-pinned version in requirements-dev.txt)
python3 -m runner.experiment configs/p0_smoke.yaml   # plan runs from a config
```

A training run is: **one YAML in `configs/` → `runner` expands seeds and
resume state → `bytelens` executes → one record per run in `logger/`**.
Seeds live in the config, never in code.

### 🔗 Provenance chain (ADR-009)

Every number resolves to exact data, split, config, code, environment, and
seed — and re-running reproduces it:

```bash
python -m logger.manifest verify        # data hashes vs. datasets/MANIFEST.json
python -m logger.verify                 # data + splits + record hash chain
python -m logger.trace <run_id>         # full chain for one run / table cell
python -m logger.repro <run_id>         # re-run and compare metrics
python -m runner.locks freeze <name> --config-hash H --split-hash H --dataset-hash H
```

Run IDs are **derived** — `sha256(config_hash | dataset_hash | split_hash |
git_sha | seed)[:12]` — and records are chained (`prev_record_hash` →
`record_hash`), so editing or deleting a line is detectable. Evaluating a
locked test window without a matching freeze lock crashes the runner, and
table generators refuse `smoke`/`pilot-10pct` runs outright. Headline
(`final`) runs require a clean git tree plus a matching lock.

---

## 🗃️ Dataset (exactly how to get it)

Primary scope: **BODMAS** only.

1. Request access from the BODMAS authors
   (`https://whyisyoung.github.io/BODMAS/`) and note the license terms.
2. Place the downloaded archive in `datasets/raw/` — **gitignored, immutable,
   never committed**. Record its SHA-256, download date, and license in
   `datasets/raw/README.md`.
3. Parse read-only with `pefile` on the host; anything execution-shaped runs
   only in `sandbox/` (no network, read-only raw mount — ADR-006).
4. Timestamps and family labels are required (time-aware and open-set splits,
   ADR-003). If coverage is unclear, **stop and ask** (AGENTS.md §9).

---

## 🏗️ Repository Layout

```
bytelens/    core library: render, regions, models, explain, attacks, defenses, eval
runner/      config-driven experiment planning (seeds, resume); execution lands in P1
logger/      structured run records (JSONL) — the source of every paper number
configs/     one YAML per experiment; the unit of reproducibility
sandbox/     Dockerfile + protocol: the only place a sample may execute
datasets/    raw/ (immutable, gitignored) · processed/ (derived) · splits/ (tracked hash lists)
models/      gitignored weights + tracked MANIFEST.md
docs/        adrs/ (decision records) · postmortems/ (incident registry)
tests/       unit/ and integration/ — offline, synthetic PEs only, never real malware
paper/       LaTeX + figure scripts generated from logger/ records
notebooks/   numbered EDA/pilots — never the source of paper numbers
```

## 🚨 Hard rules (short form — full text in AGENTS.md §2)

- **Safety:** samples are executed *only* in `sandbox/` (no network, read-only
  raw mount). Host interaction with a raw sample = read-only `pefile` parsing.
  No binaries in git — hashes and split lists only.
- **Integrity:** no number without a run ID, config, and seed in `logger/`;
  nothing fabricated or estimated; thresholds pre-registered before use;
  no robustness claim without the adaptive attack A8; negative results are
  reported.

## 🚦 Phases

| Phase | Scope | Gate |
|---|---|---|
| P0 | scaffold, CI, sandbox, ADRs | ✅ pytest + lint in CI; sandbox boundary defined |
| P1 | dedup, PE parse, 3 splits, region partition, 4 baselines | split-leakage tests pass; clean results logged |
| P2 | audits S1–S4, Grad-CAM sanity/faithfulness (5-seed pilot) | findings in `logger/` + ADRs/postmortems |
| P3 | PE editors, A1/A3/A4/A6, defenses, ECT + collapse guard, A8 | edits verified valid; adaptive attack implemented |
| gate | human go/no-go on venue | week 6 — written decision required |
| P4 | 10 seeds, ablations, figures/tables from logs | every paper number reproducible from a config |

## 📚 Documentation

- 📚 **ADR catalog:** [`docs/adrs/README.md`](docs/adrs/README.md) — decisions
  ADR-000 … ADR-009 (partition, shared resize, splits, statistics, collapse
  guard, sandbox, run records, dataset roles, provenance & traceability).
- 🔥 **Postmortem registry:** [`docs/postmortems/README.md`](docs/postmortems/README.md).
- 📜 Operating brief for agents: [AGENTS.md](AGENTS.md).
- 🏰 Conventions source:
  [Design Dungeons](https://github.com/pd241008/Design-Dungeons) — ADR format,
  conventional commits, testing architecture, ML reproducibility patterns
  (adoption recorded in [ADR-000](docs/adrs/adr-000-adopt-design-dungeons-conventions.md)).
- Changes: [CHANGELOG.md](CHANGELOG.md).

## 📝 Citation

Working title — manuscript in preparation (target venue: IEEE TIFS). A
release-ready BibTeX entry lands with the paper; until then cite as:

```bibtex
@unpublished{desai2026explainrt,
  title  = {Explanation-Aware Robustness of Image-Based Malware Classifiers:
            PE-valid Problem-Space Attacks on Predictions and Grad-CAM
            Explanations, and an Explanation-Consistency Training (ECT)
            Defense},
  author = {Desai, Prathmesh P.},
  note   = {Manuscript in preparation. Code: github.com/pd241008/ExplainRT}
}
```

---

_[pd241008](https://github.com/pd241008) · [ct-os-dev-portfolio.vercel.app](https://ct-os-dev-portfolio.vercel.app)_
