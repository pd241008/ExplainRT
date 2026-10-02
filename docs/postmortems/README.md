# 🔥 Postmortem Registry — ByteLens

Postmortems are written **when something breaks, not at the end**
(AGENTS.md §3.5). Every incident — safety, integrity, or correctness — gets
an entry here and a link from the commit or PR that fixes it.

Format: the Design Dungeons postmortem style used in
[`02-postmortems/blackice/`](https://github.com/pd241008/Design-Dungeons/tree/main/02-postmortems/blackice)
— the closest prior art for adversarial-robustness failures (phantom
robustness ceilings, dataset confounds, fabricated numbers).

## Index

No incidents yet. When the first lands:

| Postmortem | Date | Severity | Run IDs |
|---|---|---|---|
| — | — | — | — |

## Naming and contents

- Filename: `YYYY-MM-DD-short-slug.md` for dated incidents, or
  `NNN-short-slug.md` for project-lifetime lessons (BlackIce style).
- Every postmortem contains: **Summary → Impact → Timeline → Root cause →
  What worked / What failed → Corrective actions (owners + status) →
  Run IDs** (per ADR-007, incident evidence is run records, not memory).

## Rules

1. **Blameless toward people, specific about mechanisms.** Root causes name
   code paths, configs, and missing tests — not person-blame.
2. **Negative results count.** ECT collapse, A8 defeating a defense, or a
   lost comparison to canonicalization are findings: they get postmortems or
   ADR amendments, never quiet deletion (AGENTS.md §2).
3. **Safety incidents stop work.** A sandbox no-network breach or any
   near-execution of a sample on the host halts the pipeline until the
   corrective action ships (AGENTS.md §9).
4. **Corrective actions are tracked to done** in the index above, not
   "noted".
