# ByteLens 🔬

**Explanation-aware robustness of image-based malware classifiers:** PE-valid
problem-space attacks on predictions *and* Grad-CAM explanations, and an
Explanation-Consistency Training (ECT) defense.

Research code for a journal paper (target: IEEE TIFS; backup: Computers &
Security). The spec is `paper/malware_tifs_paper.tex` — names, goals G1–G3,
attacks A1–A8, audits S1–S7, metrics. **Agents and contributors: read
[AGENTS.md](AGENTS.md) before touching code.**

> **Status: P0 scaffold complete.** Layout, CI, sandbox boundary, ADR-000–007,
> logger, and runner planning are in place. Next up is P1 (data + baselines),
> which waits on **BODMAS access** and the paper source — both are
> stop-and-ask items (AGENTS.md §9). All numbers quoted anywhere must trace to
> a `logger/` run record; none exist yet, by design.

## Hard rules (short form — full text in AGENTS.md §2)

- **Safety:** samples are executed *only* in `sandbox/` (no network, read-only
  raw mount). Host interaction with a raw sample = read-only `pefile` parsing.
  No binaries in git — hashes and split lists only.
- **Integrity:** no number without a run ID, config, and seed in `logger/`;
  nothing fabricated or estimated; thresholds pre-registered before use;
  no robustness claim without the adaptive attack A8; negative results are
  reported.

## Layout

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

## Quickstart

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt -r requirements-dev.txt

pytest                     # unit tests (offline, synthetic data only)
ruff check .               # lint
python3 -m runner.experiment configs/p0_smoke.yaml   # plan runs from a config
```

A training run is: **one YAML in `configs/` → `runner` expands seeds and
resume state → `bytelens` executes → one record per run in `logger/`**.
Seeds live in the config, never in code.

## Phases

| Phase | Scope | Gate |
|---|---|---|
| P0 | scaffold, CI, sandbox, ADRs | ✅ pytest + lint in CI; sandbox boundary defined |
| P1 | dedup, PE parse, 3 splits, region partition, 4 baselines | split-leakage tests pass; clean results logged |
| P2 | audits S1–S4, Grad-CAM sanity/faithfulness (5-seed pilot) | findings in `logger/` + ADRs/postmortems |
| P3 | PE editors, A1/A3/A4/A6, defenses, ECT + collapse guard, A8 | edits verified valid; adaptive attack implemented |
| gate | human go/no-go on venue | week 6 — written decision required |
| P4 | 10 seeds, ablations, figures/tables from logs | every paper number reproducible from a config |

## Documentation

- 📚 **ADR catalog:** [`docs/adrs/README.md`](docs/adrs/README.md) — decisions
  ADR-000 … ADR-007 (partition, shared resize, splits, statistics, collapse
  guard, sandbox, run records).
- 🔥 **Postmortem registry:** [`docs/postmortems/README.md`](docs/postmortems/README.md).
- 📜 Operating brief for agents: [AGENTS.md](AGENTS.md).
- 🏰 Conventions source:
  [Design Dungeons](https://github.com/pd241008/Design-Dungeons) — ADR format,
  conventional commits, testing architecture, ML reproducibility patterns
  (adoption recorded in [ADR-000](docs/adrs/adr-000-adopt-design-dungeons-conventions.md)).
- Changes: [CHANGELOG.md](CHANGELOG.md).

## Data

`datasets/raw/` is empty until BODMAS is obtained from its owners; access,
licensing, and timestamp coverage are confirmed before any P1 work starts.
Until then the split protocols, thresholds, and tolerances stay
`Proposed`/`Draft` in the ADR catalog — nothing is decided against data we
cannot see.
