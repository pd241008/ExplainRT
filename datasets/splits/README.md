# Splits — Tracked Hash Lists

One JSON file per protocol version. Splits are the **only** dataset artifact
tracked in git (AGENTS.md §4): samples are referenced by SHA-256 hash lists,
never by file.

Planned protocols (ADR-003): `random`, `near_duplicate_proxy`, `time_aware`,
`open_set`. No split files exist yet — BODMAS access is pending (AGENTS.md §9).

Schema (ADR-009, finalizing the layout sketched in ADR-003):

- Side files: `datasets/splits/<name>/{train,val,test}.txt` — one sorted
  sha256 sample ID per line (the canonical sample ID; never paths, never
  contents).
- `splits.lock.json` — per split `<name>`: sample counts, per-side hashes,
  `split_hash` (hash of the sorted ID lists), and the split spec: algorithm
  + version, seed, window boundaries (time-aware), sampling fraction and
  month/family stratification (the 10% subsets are defined only by a frozen
  ID list plus seed), and the `dataset_hash` the split was built from.

Verify with `python -m logger.verify` (checks every split against its lock
entry); build entries with `logger.splits.make_lock_entry`.

Leakage invariants (tested in `tests/unit/test_splits.py`, P1):

- no cluster crosses splits,
- train dates < validation dates < test dates (time-aware),
- fixed seed + same input ⇒ identical split.
