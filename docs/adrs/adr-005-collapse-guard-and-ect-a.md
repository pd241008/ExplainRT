# 📜 ADR-005: Collapse guard, tolerances, and ECT-A

> **Status:** `Draft` — tolerances and ECT-A details are **deliberately not
> chosen yet**. This ADR fixes the *mechanism*; the numbers are pre-registered
> on a validation window before any ECT run uses them (hard rule, AGENTS.md
> §2: thresholds chosen before the runs that use them, never on test).
> **Date:** October 2026

---

## 🌎 Context

Explanation-Consistency Training (ECT) adds an explanation-consistency term
to training. Two failure modes are known a priori:

1. **Collapse** — the model minimizes the consistency term by flattening
   explanations (or predictions) instead of becoming genuinely robust:
   accuracy holds while explanations become uninformative, or vice versa.
   A robustness headline built on a collapsed model would be wrong.
2. **Adaptive-attack blindness** — a defense evaluated only against the
   attacks it trained on (A1/A3/A4/A6) looks better than it is; the
   adaptive attack A8 exists precisely to test this (AGENTS.md §2: no claim
   without A8).

A collapse-guard mechanism with pre-registered tolerances is the guardrail;
ECT-A is the adaptive-attack-aware variant of ECT that the guard protects.

## 🛤️ Options Considered

1. **No guard; inspect training curves manually** — human judgment after
   seeing results; exactly the practice the hard rules forbid.
2. **Guard with tolerances fixed at runtime** — numbers chosen while watching
   the runs they judge; pre-registration violated.
3. **Mechanism now, tolerances pre-registered on an earlier validation
   window, before ECT runs** ✅

---

## 🎯 Decision

> [!IMPORTANT]
> **Every ECT/ECT-A run is wrapped by a collapse guard that evaluates
> pre-registered criteria on the validation window after each epoch:
> (a) clean accuracy within tolerance of the non-ECT baseline,
> (b) explanation quality (faithfulness metric from `bytelens.explain`)
> within tolerance of the baseline, (c) consistency term not degenerating
> (non-zero variance across batches). Breach ⇒ run marked `collapsed` in its
> logger record, training stops, and the result is reported as a negative
> result — never silently dropped.**

Mechanism (fixed now):

- The guard is a wrapper in `bytelens.explain` + `runner` that writes a
  `guard` section into the run record: criteria, values, verdict.
- Tolerances are three numbers (relative deltas for a and b; a variance
  floor for c). They are chosen once, on the P2 validation window, written
  into this ADR as an amendment, and only then used in P3 runs.
- ECT-A: ECT plus adversarial example generation through the adaptive attack
  A8 during training, with the same tuning budget as every other defense
  (Arp et al. pitfall P5 — no extra tuning for ECT/ECT-A).

## 🧠 Reasoning

A guard whose numbers are chosen after seeing runs is decoration; the value
comes entirely from fixing the numbers on earlier data. Marking collapse as a
reportable outcome converts a potential silent failure into a paper finding
(AGENTS.md §2: report negative results; postmortem if ECT loses to
canonicalization).

## ⚖️ Consequences

- **Good:** 🟢 A collapsed ECT cannot produce a headline claim — the guard
  verdict is machine-readable in the run record.
- **Good:** 🟢 Negative results arrive with evidence attached (guard values
  per epoch), ready for the postmortem registry.
- **Bad:** 🔴 Tolerance choices can be wrong in either direction (false
  alarms kill healthy runs; loose tolerances miss collapse) — the amendment
  records the reasoning so mistakes are auditable.
- **Bad:** 🔴 The guard adds a validation-pass per epoch; acceptable at P3
  scale, revisited if sweep size grows.

## 🔄 Revisit When

- P2 validation data exists → amend this ADR with the three tolerance
  numbers, the chosen faithfulness metric, and the window definition.
- A8 defeats ECT/ECT-A → postmortem + this ADR records what the adaptive
  attack exploited (gradient masking? budget leakage?).
- A second consistency metric enters the paper → extend criteria with the
  same pre-registration discipline.
