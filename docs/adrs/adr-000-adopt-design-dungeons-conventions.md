# 📜 ADR-000: Adopt Design Dungeons conventions; verified source corrections

> **Status:** `Decided`
> **Date:** October 2026

---

## 🌎 Context

AGENTS.md §3 mandates the owner's Design Dungeons playbook
(`github.com/pd241008/Design-Dungeons`) as the conventions source for this
repo, and explicitly warns: *"not all were verified by whoever wrote this
brief."* The cited "read before starting" paths did not all resolve against
the live repository at scaffold time.

This scaffold is the first code in the repo, so conventions had to be settled
before the first commit, not after.

## 🛤️ Options Considered

1. **Follow AGENTS.md §3 exactly as written** — risk: dead references and a
   template that does not match the real playbook.
2. **Verify every cited path against the live Design-Dungeons repo and amend**
   — small upfront cost, removes all dead references. ✅
3. **Ignore Design Dungeons and keep only AGENTS.md** — contradicts the brief
   itself ("Where they differ from this file, Design Dungeons wins").

---

## 🎯 Decision

> [!IMPORTANT]
> **Adopt Design Dungeons conventions for ByteLens, with the brief's citation
> errors corrected against the live repo. Where the brief and the playbook
> disagree on conventions, the playbook wins and the difference is recorded in
> an ADR; where the hard rules (AGENTS.md §2) and anything else disagree, the
> hard rules win.**

Verified corrections to the AGENTS.md §3 path list:

| Brief said | Live repo has |
|---|---|
| `01-documentation/adrs/adr-template.md` | `01-documentation/adrs-templates/adr-template.md` |
| `05-git-and-versioning` (README) | `05-git-and-versioning/05-git-and-versioning.md` |
| `13-ml-and-research/research-patterns.md` | unchanged — verified correct |
| `02-postmortems/blackice/` | unchanged — verified present (closest prior art for adversarial-robustness failures) |
| `06-environments/environment-standards.md` | unchanged — verified correct |
| `10-testing/testing-architecture.md` | unchanged — verified correct |

AGENTS.md as committed already reflects the corrected paths.

Conventions adopted concretely in this scaffold:

- **Conventional commits** `type(scope): subject`, imperative, ≤ ~50 chars,
  body explains why (Design Dungeons §05).
- **ADR format** with Consequences and Revisit When (Design Dungeons §01).
- **Postmortem registry** opened at scaffold time, entries on incidents as
  they happen (Design Dungeons §02).
- **Root-level decoupling and visibility first**: `logger/` and `runner/` are
  first-class root directories (Design Dungeons §00/§03).
- **Research layout**: numbered notebooks, `datasets/{raw,processed}`, tracked
  split lists only, strictly pinned `requirements.txt` (§13).
- **Honesty-first reproducibility**: every number traces to a run record;
  nothing fabricated, nothing hand-typed (§13, ChaosSeal pattern).
- **Tests are offline and deterministic**; no live external dependencies
  (§10 testing architecture).

## 🧠 Reasoning

The brief anticipated its own drift ("not all were verified") and ordered the
difference recorded in an ADR. Verifying against the live repo at scaffold
time was cheaper than discovering a broken reference later, and it made the
template concrete: this file's structure is the real Design Dungeons ADR
template, not a reconstruction of it.

## ⚖️ Consequences

- **Good:** 🟢 Every convention traces to a checked source; ADRs, commits, and
  tests follow one template from commit one; future agents reading AGENTS.md
  get correct paths.
- **Bad:** 🔴 Two convention documents now exist (AGENTS.md and the playbook);
  they can drift apart. This ADR is the tiebreaker record.
- **Bad:** 🔴 Playbook sections marked "coming soon" (code review) offer no
  guidance; ByteLens fills those gaps from AGENTS.md hard rules.

## 🔄 Revisit When

- The Design-Dungeons repo restructures paths or templates.
- A genuine conflict appears between playbook conventions and AGENTS.md §2
  hard rules (hard rules win; the conflict gets its own ADR).
- A second contributor joins and the single-maintainer workflow assumptions
  (branch naming without namespaces) stop holding.
