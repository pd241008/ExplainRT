# 📚 ADR Catalog — ByteLens

Architecture Decision Records use the
[Design Dungeons ADR template](https://github.com/pd241008/Design-Dungeons/blob/main/01-documentation/adrs-templates/adr-template.md):
Context, Options Considered, Decision, Reasoning, **Consequences**, **Revisit When**.

New ADRs get the next free `NNN`. Statuses: `Draft → Proposed → Decided → Deprecated`.
Pre-registration matters here: thresholds and tolerances must be `Decided` in an
ADR **before** the runs that use them (hard rule, AGENTS.md §2).

| ADR | Title | Status | Date |
|---|---|---|---|
| [ADR-000](adr-000-adopt-design-dungeons-conventions.md) | Adopt Design Dungeons conventions; verified source corrections | Decided | 2026-10 |
| [ADR-001](adr-001-canonical-flag-based-region-partition.md) | Canonical flag-based PE region partition | Decided | 2026-10 |
| [ADR-002](adr-002-shared-differentiable-resize.md) | Shared differentiable resize for training, inference, and attacks | Decided | 2026-10 |
| [ADR-003](adr-003-split-protocol.md) | Split protocol: random, near-duplicate, time-aware, open-set | Proposed | 2026-10 |
| [ADR-004](adr-004-multi-seed-and-statistics-protocol.md) | Multi-seed and statistics protocol | Proposed | 2026-10 |
| [ADR-005](adr-005-collapse-guard-and-ect-a.md) | Collapse guard, tolerances, and ECT-A | Draft | 2026-10 |
| [ADR-006](adr-006-safe-malware-handling-sandbox-boundary.md) | Safe malware handling and the sandbox boundary | Decided | 2026-10 |
| [ADR-007](adr-007-run-records-and-reproducibility.md) | Run records and reproducibility | Decided | 2026-10 |
| [ADR-009](adr-009-provenance-hashing-and-result-traceability.md) | Provenance, hashing, and result traceability | Decided | 2026-10-05 |

Postmortems live in the separate registry: [`docs/postmortems/README.md`](../postmortems/README.md).
