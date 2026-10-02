# 📜 ADR-001: Canonical flag-based PE region partition

> **Status:** `Decided`
> **Date:** October 2026

---

## 🌎 Context

Every explanation (RQ3) and every attack budget check (RQ4) needs to know
which logical region of a PE each byte belongs to: headers, section table,
code, data, import data, slack, appended data. Two implementations of the
same idea exist across the literature: classify a section by its **name**
(`.text` → code) or by its **flags** (Section Table `IMAGE_SCN_MEM_EXECUTE` +
`IMAGE_SCN_CNT_CODE`, cross-checked against `AddressOfEntryPoint` and RVA
ranges). Section names are attacker-controlled strings: renaming `.text` to
`.data` costs an attacker nothing, and name-based region logic then
mislabels the attack — corrupting both explanation aggregates (region masses)
and budget enforcement (which bytes may change).

BODMAS samples include packed and section-modified binaries, so the mislabel
case is the common case, not an edge case.

## 🛤️ Options Considered

1. **Name-based partition** — simple, but defeated by section renaming;
   silently wrong under exactly the attacks we study.
2. **Flag-based partition, one canonical implementation** — immune to renames;
   must define deterministic tie-breaking for overlapping/odd cases. ✅
3. **No partition; pixel-level explanations only** — cheaper, but region
   masses (S-audits, ECT consistency term) become undefined; loses a core
   paper deliverable.

---

## 🎯 Decision

> [!IMPORTANT]
> **ByteLens uses one canonical, flag-based partition implemented only in
> `bytelens.regions`. Classification uses section characteristics flags and
> RVA ranges, never section names. Every byte receives exactly one label,
> with a deterministic precedence order for overlaps and an explicit
> `unknown` label — never silence.**

Label set (versioned; bump the version on any change):

`header`, `section_table`, `code`, `data`, `imports`, `relocs`, `resources`,
`tls`, `overlay`, `slack`, `unknown`.

Precedence for overlapping byte ranges: `header` > `section_table` > section
content (by RVA order) > `overlay`. Section slack (raw-size minus virtual
demand) is always its own `slack` label so budget rules can forbid or allow
it explicitly per attack.

## 🧠 Reasoning

Flag-based classification survives the renaming attack by construction, and a
single implementation shared by explain/attack/eval code removes the
cross-pipeline inconsistency class entirely. The cost is up-front definition
work (precedence rules, versioned labels) — cheap compared to silently
invalid region aggregates discovered at review time. The `unknown` label makes
parser gaps visible in aggregates instead of hiding them.

## ⚖️ Consequences

- **Good:** 🟢 Explanation region masses and attack budget checks share one
  partition; renamed-section tests can enforce the property directly.
- **Good:** 🟢 Versioned labels make partition changes auditable across run
  records (ADR-007).
- **Bad:** 🔴 Parser edge cases (malformed section tables, TLS overlaps) must
  resolve through explicit precedence rules; new cases require a version bump
  and re-checking stored aggregates.
- **Bad:** 🔴 `bytelens.regions` becomes a hard dependency of three domains;
  its tests are effectively integration-critical.

## 🔄 Revisit When

- A byte layout appears in BODMAS that the precedence rules cannot classify
  without ambiguity (counts land in the `unknown` bucket — revisit above a
  pre-registered threshold).
- The paper adds datasets with non-PE formats (supplement scope; needs a new
  ADR).
- A second partition granularity (e.g., function-level) becomes needed for
  S5–S7 audits.
