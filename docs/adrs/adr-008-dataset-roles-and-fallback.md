# ADR-008: Dataset roles, combination rules, and BODMAS fallback

- **Status:** Proposed
- **Date:** 2026-10-05
- **Supersedes:** scope line in AGENTS.md ("BODMAS only"); amends ADR-003 (split protocol)

## Context

The primary corpus (BODMAS binaries) depends on an access request that may be denied or delayed. BODMAS also ships feature vectors and metadata separately; those are usable now but support only the non-image path (no byte-images, Grad-CAM, or PE edits). Public alternatives exist, each with different strengths and limits:

| Dataset | Strengths | Limits |
|---|---|---|
| BODMAS features + metadata | 57k malware, 581 families, first-seen timestamps (Aug 2019 – Sep 2020) | Features only; no bytes. Binaries need approval. |
| BODMAS binaries (pending) | Time-aware family classification with raw PEs | Access not guaranteed; terms restrict sharing |
| MOTIF | 3,095 disarmed PEs, 454 expert-labeled families, public | Small; many rare families; disarmed (cannot run); dates are report-based |
| SOREL-20M | ~10M benign + ~10M disarmed malware; time-aware detection and drift at scale | **Verify:** labels are category tags, not families; binaries are very large, so a subset is required |
| MalwareBazaar | Fresh, timestamped, family signatures | Noisy labels; live malware; account/API key and terms to verify |
| Benign PEs | Safe to execute; supports execution-verified edits | Not malware; pseudo-families only |

## Decision

1. **Each dataset is used for what it is good at and is reported separately.** No pooled training set.
2. **Roles**
   - BODMAS binaries (if granted): primary time-aware family classification, region attribution, PE-valid attacks.
   - BODMAS features/metadata (available now): LightGBM baseline, frozen time-aware and open-set splits (as sha256 lists), AUT and drift curves, category analysis.
   - MOTIF: clean-label family classification (group-aware, filtered to families with enough samples) and, if BODMAS binaries are granted, a test-only cross-corpus set via an alias map.
   - SOREL-20M: time-aware detection, drift, and shortcut analysis on a stratified-by-month subset.
   - MalwareBazaar: optional fresh-sample drift test, only after terms and sandbox rules are confirmed.
   - Benign PEs: execution-based verification of PE edits; smoke tests (tagged `smoke`, never in paper tables).
3. **Combination rules**
   - Deduplicate by SHA-256 across all corpora; remove cross-corpus overlaps from test sets.
   - Identical preprocessing for all corpora; normalize disarm fields (Subsystem, Machine) so headers cannot reveal the source.
   - Add shortcut audit **S8**: predict the source dataset from the rendered image; a high score invalidates cross-corpus comparisons.
   - Splits and time windows are defined per dataset; label spaces are never merged.
   - Report each dataset separately, plus explicit cross-corpus results.
4. **Edit validation.** Execution-based verification runs on benign PEs only. Edits on disarmed malware are verified structurally (parse, alignment, loader-field consistency) and reported as structural-only.
5. **Dataset adapter interface.** All loaders implement one adapter (`iter_samples`, `metadata`, `bytes(sha)`, `splits`) so the pipeline is dataset-agnostic.

## Scenarios

- **A: BODMAS binaries granted.** BODMAS is primary; MOTIF and SOREL add cross-corpus and drift results. The abstract's time-aware family claim stands.
- **B: BODMAS binaries not granted.** Primary evidence becomes MOTIF (family, group-aware) + SOREL (time-aware detection/drift) + BODMAS features (time-aware family, feature-based only) + benign PEs (execution checks). Drop time-aware family claims for image models; reword abstract and Table III accordingly. Re-evaluate venue (Computers & Security becomes the more realistic target unless SOREL and the attack results are strong).
- **Trigger for B:** no reply 14 days after the request is sent (one follow-up at day 7), or an explicit decline.

## Alternatives considered

- Pooling all corpora into one training set: rejected (source leakage via disarmed headers, incompatible time axes and label spaces, cross-corpus duplicates).
- Waiting for BODMAS before building anything: rejected (blocks the pipeline and the week-6 gate).
- Using only MOTIF: rejected (too small for time-aware claims).

## Consequences

- Paper claims are scoped per dataset; more tables, but each is defensible.
- Extra work: adapters, alias map for MOTIF families, SOREL subset sampling, audit S8.
- Edit-validity claims on malware are weaker (structural only) in Scenario B and for MOTIF/SOREL; this must be stated in Limitations.
- AGENTS.md primary scope must be updated to reference this ADR.

## Revisit When

- BODMAS access is granted or denied.
- SOREL labels or access terms differ from what is assumed here.
- MalwareBazaar terms prohibit the intended use.
- The S8 audit shows the source dataset is predictable after normalization.
- The week-6 go/no-go decision is made.
