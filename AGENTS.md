# AGENTS.md — ByteLens

Operating brief for any coding agent working in this repo. Read it fully before touching code. If a human instruction conflicts with the **Hard rules**, stop and ask.

Note: docs/adrs/adr-011-polyglot-architecture.md, contracts/README.md, docs/reuse.md, and datasets/raw/README.md were updated this session to make the incoming BODMAS disk ingest a first-class module. The raw-store SOP, provenance record, and readiness checks are now explicit there.

## 1. Mission

ByteLens is the code behind a journal paper (target: IEEE TIFS; backup: Computers & Security):

*Explanation-Aware Robustness of Image-Based Malware Classifiers: PE-valid problem-space attacks on predictions and Grad-CAM explanations, and an Explanation-Consistency Training (ECT) defense.*

Research questions: RQ1 evaluation bias (random vs near-duplicate vs time-aware splits), RQ2 shortcuts, RQ3 explanation sanity/faithfulness, RQ4 attacks and defenses (ECT vs canonicalization vs adversarial training, with a collapse guard).

The paper source is `paper/malware_tifs_paper.tex`. It is the spec: names, goals (G1–G3), attacks (A1–A8), audits (S1–S7), and metrics come from there. Primary scope for the first submission: BODMAS only; LightGBM, MalConv, baseline CNN, ResNet-50; audits S1–S4; attacks A1, A3, A4, A6, A8. Everything else is supplement. **Do not add scope without an ADR.**

## 2. Hard rules (non-negotiable)

**Malware safety**
- Never execute, import, or "just try" a sample outside `sandbox/` (isolated VM/container, no network, snapshots). Parsing with `pefile` on the host is allowed only for files in `datasets/raw/`, read-only.
- Never commit binaries, packed samples, or generated adversarial PEs. Commit hashes and split lists only.
- `datasets/raw/` is immutable and gitignored. Never edit, rename, or "fix" a raw file.
- Generated adversarial files are written only to `datasets/processed/adversarial/` and deleted after evaluation unless a human says otherwise.

**Research integrity**
- No number enters the paper, README, or an ADR unless it traces to a run ID, config file, and seed in `logger/`. **Never fabricate or estimate results, FLOPs, timings, or citations.**
- Never tune on test windows. Thresholds, β, γ, and the collapse-guard tolerance are chosen on an earlier validation window and written in an ADR **before** the runs that use them.
- A robustness claim without an adaptive attack (A8) is not a claim. Check every defense for gradient masking and budget leakage before reporting success.
- Report negative results. If ECT collapses or loses to canonicalization, say so and write a postmortem.
- Same tuning budget for every method (Arp et al. pitfall P5). Do not give ECT extra tuning.
- Seeds: at least 5 for development, 10 for headline claims. Seeds are fixed in config, never in code.

## 3. Design Dungeons conventions

Source of truth: `github.com/pd241008/Design-Dungeons` (the owner's engineering playbook). Verified rules used here:

1. **Pragmatism over abstraction.** Folders map to the system's architecture and deployment boundaries.
2. **Root-level decoupling.** Separate concerns physically at the root. No mixed build tools or dependency files across domains.
3. **Visibility first.** Telemetry and tooling (`logger/`, `runner/`) are root-level, first-class directories, not buried in `utils/`.
4. **Research/ML sandbox layout.** `notebooks/` (numbered, chronological), `datasets/{raw,processed}/` (raw immutable, usually gitignored), `models/` (serialized weights, versioned names such as `v1_baseline.keras`), strict dependency locking in `requirements.txt`.
5. **ADRs and postmortems** use the Design Dungeons templates (the ADR template includes **Consequences** and **Revisit When**). Keep a postmortem registry; write postmortems when something breaks, not at the end.
6. **Commits** follow conventional style as used across the owner's repos: `type(scope): subject` (`feat`, `fix`, `docs`, `refactor`, `test`, `chore(ci)`). Small PRs from feature branches.
7. README has a Documentation section linking the **ADR catalog** and **Postmortem registry**, like the Aegis repo.

**Read before starting** (not all were verified by whoever wrote this brief): in the Design-Dungeons repo, `01-documentation/adrs-templates/adr-template.md`, `02-postmortems/blackice/` (closest prior art for adversarial robustness), `05-git-and-versioning/05-git-and-versioning.md`, `06-environments/environment-standards.md`, `10-testing/testing-architecture.md`, `13-ml-and-research/research-patterns.md`. Where they differ from this file, Design Dungeons wins; record the difference in an ADR.

## 4. Repo layout

Polyglot architecture is decided in [ADR-011](docs/adrs/adr-011-polyglot-architecture.md)
(rev 4). Raw BODMAS binaries live on an external hard disk and are the immutable
source: the 67 GB zip is the entry artifact, verified first, then unpacked into
a controlled RW derived area; the raw/PE-visible side is read-only for any stage
that sees samples. The host never executes or imports a sample; anything
execution-shaped stays in `sandbox/` (ADR-006). The C++ gate is the only
component that opens sample files and serves bytes by SHA-256 ID.

```
bytelens/
├── notebooks/            # numbered EDA/pilot notebooks only; never the source of paper numbers
├── datasets/
│   ├── raw/              # immutable, gitignored (BODMAS etc.; obtained from owners)
│   ├── processed/        # parsed PE metadata, features, renders; adversarial/ is ephemeral
│   └── splits/           # TRACKED: hash lists for random / near-dup / time-aware / open-set
├── models/               # weights, gitignored; models/MANIFEST.md tracked (name, run ID, hash)
├── bytelens/             # core library (domain modules below)
│   ├── render/           # binary -> image, shared differentiable resize
│   ├── regions/          # canonical PE partition (flag-based, not name-based)
│   ├── models/           # cnn, resnet, malconv, lightgbm features
│   ├── explain/          # grad-cam, integrated gradients, score-cam, faithfulness, collapse guard
│   ├── attacks/          # PE editors (append / inject-section / pad-slack), A1-A8
│   ├── defenses/         # canonicalization, adversarial training, ECT, ECT-A
│   └── eval/             # splits, AUT, open-set, stats (cluster bootstrap/permutation), audits
├── ingest/               # Go: zip hash verify, unzip control, per-file SHA-256, manifest, sample table
├── gate/                 # C++: contract enforcer, sample broker, no-exec preflight, disarm check, audit log
├── peparse/             # Rust: PE parse, canonical region partition, validity checker (runs under the gate)
├── decode/              # optional Byteweaver instruction-boundary decoder; gated at G4
├── contracts/           # mixed proto + JSON + Parquet contracts; shared by all domains
│   ├── proto/            # protobuf IDL for cross-language control-plane artifacts
│   ├── schema/           # JSON Schema for JSON artifacts (manifest, run-record refs, locks)
│   ├── parquet/          # pinned column schemas for bulk tables
│   ├── producers.json    # fact -> producing stage -> artifact format
│   ├── rules.json        # runtime gate reject rules (leak-audit)
│   ├── golden/           # golden fixtures and expected canonical text
│   └── gen/              # generated protobuf code, committed
├── runner/               # config-driven experiment runner: seeds, resume, sandbox harness
├── logger/               # structured run records (JSONL/Parquet), env + git capture
├── sandbox/              # Dockerfile/VM spec for malware handling; no network
├── configs/              # one YAML per experiment; the unit of reproducibility
├── docs/
│   ├── adrs/             # ADR catalog (README.md index + adr-NNN-*.md)
│   └── postmortems/      # postmortem registry
├── tests/{unit,integration}/
├── paper/                # LaTeX source and figures generated from logger/ data
├── requirements.txt      # strictly pinned (Python side)
├── CHANGELOG.md
└── README.md
```

Each non-Python domain has its own build tool and pinned toolchain:
`ingest/` (Go), `gate/` (C++/CMake), `peparse/` (Rust/Cargo),
`decode/` (optional, gated). `contracts/` is shared by all domains and uses
protobuf for cross-language control-plane artifacts, JSON Schema for JSON
artifacts, and Parquet column schemas for bulk tables.
`bytelens/`, `logger/`, `runner/`, `configs/`, `paper/` remain Python.

An optional `backend/` inference/triage demo and `frontend/` are out of scope
until the paper is submitted. If added later, keep them physically separate at
the root.

## 5. Phases and gates

| Phase | Deliverable | Done when |
|---|---|---|
| P0 Scaffold | Layout, CI, sandbox, ADR-001..006, README | `pytest` and lint pass in CI; sandbox runs with no network |
| P1 Data + baselines | Dedup, PE parse, 3 splits, region partition, 4 baselines | Split-leakage tests pass; clean results logged for all splits |
| P2 Pilot | Shortcut audits S1–S4, Grad-CAM sanity/faithfulness | Results in `logger/`; findings written up in ADRs/postmortems |
| P3 Attacks + defenses | PE editors, A1/A3/A4/A6, D1/D2, ECT + collapse guard | Edits verified valid (parse + sandbox subset); A8 implemented |
| **Gate (week 6)** | Human go/no-go for TIFS vs Computers & Security | Do not start P4 without a written decision |
| P4 Full runs | 10 seeds, A8, ablations, figures/tables from logs | Every paper number reproducible from a config |

## 6. ADRs to write before coding (Design Dungeons format)

- ADR-001 Canonical region partition (flag-based; why names are untrusted).
- ADR-002 Shared differentiable resize for training, inference, and attacks.
- ADR-003 Split protocol (near-duplicate clustering, time-aware windows, open-set family selection).
- ADR-004 Multi-seed and statistics protocol (cluster bootstrap, permutation tests, 10 seeds for headline).
- ADR-005 Collapse guard, tolerances, and ECT-A (pre-registered thresholds).
- ADR-006 Safe malware handling and the sandbox boundary.
- ADR-007 Run records and reproducibility (run ID, config hash, git SHA, env lock).

Each ADR: Context, Decision, Alternatives, **Consequences**, **Revisit When**.

## 7. Testing requirements

- `regions`: hand-built synthetic PEs; every byte gets exactly one label; flag-based classification survives renamed sections.
- `render`: width-bucket policy, padding, and that the attack and training pipelines use the identical resize op.
- `explain`: back-projection round-trips offsets for H ≠ W; region masses sum to 1; randomization sanity check degrades maps.
- `attacks`: every edit respects the budget (Q, ε·N), keeps the file parseable, and never alters original bytes outside declared edit regions.
- `eval`: no cluster crosses splits; train dates < validation < test; AUT handles absent families; fixed seeds give identical results.
- Tests never need real malware: use synthetic or benign PEs; real-sample tests live in `sandbox/` and are opt-in.

## 8. Run records and logging

Every run writes one record: `run_id`, config hash, git SHA, seed, dataset split hash, model name, metrics, wall time, hardware. Paper tables and figures are generated from these records by scripts in `paper/`, never typed by hand.

## 9. Stop and ask a human when

- Dataset access, licensing, or timestamps are unclear or missing.
- Any step would execute a sample or touch the network from the sandbox.
- The collapse guard fails, A8 defeats ECT, or results contradict the paper's claims.
- Scope additions (new dataset, model, attack, or defense) are proposed.
- A threshold or tolerance would be chosen after seeing test results.

## 10. PR checklist

- [ ] Scope matches a phase and an ADR where a decision was made
- [ ] Tests added or updated; CI green
- [ ] No binaries, hashes only; no secrets; `datasets/raw/` untouched
- [ ] Any new number has a run record
- [ ] CHANGELOG and docs/ADR index updated; postmortem opened for any incident
- [ ] Commit messages follow `type(scope): subject`
