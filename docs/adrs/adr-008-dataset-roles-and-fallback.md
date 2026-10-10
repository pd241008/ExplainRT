# ADR-008 (rev 2): Dataset roles, controlled combination, and BODMAS fallback

- **Status:** Proposed (revision 2; replaces rev 1 of 2026-10-05)
- **Date:** 2026-10-09
- **Supersedes:** scope line in AGENTS.md ("BODMAS only"); amends ADR-003 (split protocol)

## Context

The primary corpus (BODMAS binaries) depends on an access request that may be denied or delayed. Many other public corpora exist, each covering part of what BODMAS provides (raw binaries, first-seen dates, curated families). Items marked **verify** were read from repo/paper summaries only and must be checked against the dataset documentation and licenses before use.

| Dataset | Binaries | Time information | Labels | Feature format | Notes |
|---|---|---|---|---|---|
| BODMAS features + metadata | No | First-seen (Aug 2019 – Sep 2020) | 581 curated families | EMBER v2 (2381) | Public npz via official README (verify link and terms) |
| BODMAS binaries | Yes | First-seen | 581 families | EMBER v2 | Pending approval |
| EMBER2024 | No (hashes + VT retrieval code only) | VT first upload (Sep 2023 – Dec 2024) | 6,787 ClarAVy families | **EMBER v3** | Free download; v3 features are not compatible with v2 |
| SOREL-20M | Yes, disarmed (~8 TB; use a subset) | First/last seen (2017 – Apr 2019) | Tags, not families (verify) | EMBER v2 | Free via S3 under its terms |
| MOTIF | Yes, disarmed | Report dates (2016 – 2021) | 454 expert families | n/a | Public; small, many rare families |
| MalwareBazaar | Yes, live | Likely first-seen (verify) | Signatures, noisy | n/a | Free auth key; verify terms |
| RawMal-TF | Yes, live (~160 GB) | Not found per sample (verify) | 14 types, 17 families | EMBER-compatible | Drive link; manual distribution |
| ERMDS(-X) | Malware binaries (verify) | 2022 | Labels + families | EMBER v2 | Obfuscation, packing, source-obfuscation variants |
| TRITIUM | No | ~2022 | Includes a ~14k subset of families unseen in BODMAS | EMBER v2 | MalwareBazaar-derived; features only |
| INFERNO | No | n/a | ~1.4k red-team / C2 samples | EMBER v2 | Small; evasive-malware test |
| Benign PEs | Yes | n/a | Pseudo-families (smoke only) | n/a | Execution-based edit verification |

VirusShare (invitation-only, no labels) is not planned.

## Decision

1. **Combining datasets is allowed only as a named experimental condition, never as a silent default.** Every result states its training regime.
2. **Training regimes (reported separately)**
   - **R1 single-source:** train and test within one dataset (per-dataset time-aware and near-duplicate-aware splits).
   - **R2 leave-one-dataset-out (LODO):** train on all other compatible datasets, test on the held-out dataset.
   - **R3 pooled:** train on the union of the train splits; evaluate on each dataset's own locked test split, per dataset.
3. **Rules for any combination**
   - Deduplicate across datasets by SHA-256 (and by near-duplicate hash where bytes exist) *before* splitting.
   - Define splits per dataset first (frozen hash lists), then union the **train** parts only. Test windows stay per dataset and locked.
   - **Feature compatibility:** pool only EMBER-v2 (2381-feature) sources (BODMAS, SOREL, ERMDS, TRITIUM, INFERNO). EMBER2024 uses v3 features and stays a separate track unless v2 features can be re-extracted from binaries.
   - **Labels:** do not merge label spaces silently. Maintain a harmonization/alias table in `datasets/`; pooled *family* experiments use only harmonized families above a minimum count. Otherwise pool for detection only.
   - **Class-source confound:** every source in a pooled *detection* experiment must contribute both classes. If it cannot (e.g., malware-only sources), run family classification (malware-only) instead. Never pair malware from one source with benign from another as the only contrast.
   - **Normalization:** normalize disarm fields (Subsystem, Machine) and header time fields in every corpus before rendering or featurizing.
   - **Source balance:** cap each source's share of training batches with sampling weights so large sets (SOREL) do not drown small ones.
   - **ERMDS variants:** group all variants of an original sample into the same split.
   - **TRITIUM and INFERNO are test-only by default** (they were built as drift and unseen-family tests). Using them for training is a separate, labeled R3 variant, and then not as their own test.
   - **Audit S8:** predict the source dataset from the features and from the rendered image. Report the result; a high score invalidates cross-source claims for that experiment.
4. **Time handling.** Pooled experiments also report dataset-level temporal order (train on earlier sources, test on later ones, e.g., SOREL and BODMAS then ERMDS and TRITIUM), noting that time is confounded with source. Within-dataset time-aware splits remain the primary temporal evidence.
5. **Roles**
   - Feature track: BODMAS npz, SOREL features, ERMDS, TRITIUM, INFERNO (R1/R2/R3); EMBER2024 as its own large-scale time-aware benchmark.
   - Image/PE-edit track (needs bytes): BODMAS binaries if granted; otherwise RawMal-TF, MalwareBazaar, MOTIF, a month-stratified SOREL subset, ERMDS malware binaries (verify).
   - Edit verification: execution-based on benign PEs and, where sandbox rules allow, on live malware; structural-only on disarmed corpora (stated in Limitations).
6. **Dataset adapter interface.** All loaders implement one adapter (`iter_samples`, `metadata`, `bytes(sha)`, `splits`).
7. **Coverage test (optional).** Check how many EMBER2024 hashes MalwareBazaar can supply as binaries; proceed only if overlap is large enough and terms allow.

## Scenarios

- **A: BODMAS binaries granted.** BODMAS is primary for the image track; other sets add R2/R3 and drift results.
- **B: not granted.** The image track uses the binary sources above; time-aware family claims for image models are dropped or restricted to what the available timestamps support; the abstract and dataset table are reworded. Re-evaluate venue.
- **Trigger for B:** no reply 14 days after the request, or an explicit decline.

## Options considered

- Pooling everything into one default training set: rejected (source leakage, class-source confounds, incompatible feature versions and label spaces, time confounded with source).
- Single-source only: rejected (wastes available data and the cross-corpus question).
- Mixing EMBER2024 v3 with v2 features: rejected (incompatible).

## Consequences

- More experiments and reporting (three regimes, S8 audit, harmonization table), but each claim is defensible.
- Related work must position the cross-dataset angle honestly: other studies already evaluate cross-dataset detection; the contribution is the image and explanation-robustness angle.
- Weaker edit-validity claims on disarmed corpora.
- AGENTS.md primary scope must reference this ADR.

## Revisit When

- BODMAS access is granted or denied.
- Any "verify" item turns out wrong (labels, access terms, per-sample dates, binaries in ERMDS or RawMal-TF).
- S8 shows the source is predictable after normalization.
- The week-6 go/no-go decision is made.
