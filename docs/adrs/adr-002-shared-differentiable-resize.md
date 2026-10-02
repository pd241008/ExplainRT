# 📜 ADR-002: Shared differentiable resize for training, inference, and attacks

> **Status:** `Decided`
> **Date:** October 2026

---

## 🌎 Context

Image-based malware classifiers consume a rendered image of the binary:
byte sequence → width bucket → pad → resize to network input size (e.g.
224×224 for ResNet-50). The same transformation runs in three places:
training, inference/evaluation, and inside the attack loop. A8
(adaptive, gradient-based attack) backpropagates through it, so the resize
must be differentiable end-to-end.

If the three call sites use different resize implementations — the classic
failure mode, e.g. PIL-bilinear in training and torch-bilinear in attacks —
then attack success is measured against a model that never existed, and
faithfulness audits inherit the gap. Prior adversarial-ML work has repeatedly
failed on exactly this class of mismatch (see Design Dungeons
`02-postmortems/blackice/`).

## 🛤️ Options Considered

1. **Per-pipeline resize ops** — flexible; guarantees train/attack mismatch
   and invalidates A8 transferability claims.
2. **One shared op, one import path** — everything resolves to the same
   callable; differentiability required. ✅
3. **Same code, two backends (CPU render / GPU attack)** — tempting for
   speed; re-introduces the mismatch class through backend numeric
   differences.

---

## 🎯 Decision

> [!IMPORTANT]
> **One shared, differentiable resize op lives in `bytelens.render` and is
> the only resize used by training, inference, and attack code. Attack and
> evaluation code import it from there; redefining resize anywhere else is a
> review-blocking violation. Width-bucket choice, padding value, and output
> size come from the config, never inline constants.**

Properties enforced by `tests/unit/test_render.py` (P1):

- determinism: same bytes + config ⇒ identical output;
- differentiability: gradients flow through the op (required by A8);
- identity: the object used by the attack pipeline is the very same callable
  object used by the training pipeline (single import path).

## 🧠 Reasoning

The attack's effect is only interpretable relative to the exact preprocessing
the model was trained and evaluated with. A single source of truth is the
cheapest mechanism that makes "same preprocessing" verifiable rather than
promised: a unit test can assert identity of the callable itself, not
approximate equivalence of two implementations.

## ⚖️ Consequences

- **Good:** 🟢 A8 gradients are computed through the true pipeline; faithfulness
  audits (deletion/insertion) measure the deployed transform.
- **Good:** 🟢 Render settings are config-pinned and hash into the config hash
  (ADR-007), making render drift visible in run records.
- **Bad:** 🔴 A GPU-accelerated attack path must either reuse the identical op
  or add a backend-parity test; numeric parity becomes an explicit
  maintenance obligation.
- **Bad:** 🔴 Changing the resize (e.g. different interpolation) invalidates
  comparability with all prior runs — a config-breaking change that requires
  an ADR amendment.

## 🔄 Revisit When

- A model enters scope that needs a fundamentally different preprocessing
  (e.g. MalConv consumes raw bytes) — it simply bypasses render, no change.
- Attack throughput forces a second backend (add backend-parity tests first).
- Width-bucket policy shows bucket-boundary artifacts in audits (S-audits may
  motivate a policy change; that changes results semantics ⇒ ADR amendment).
