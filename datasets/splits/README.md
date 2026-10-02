# Splits — Tracked Hash Lists

One JSON file per protocol version. Splits are the **only** dataset artifact
tracked in git (AGENTS.md §4): samples are referenced by SHA-256 hash lists,
never by file.

Planned protocols (ADR-003): `random`, `near_duplicate`, `time_aware`,
`open_set`. No split files exist yet — BODMAS access is pending (AGENTS.md §9).

Schema (to be finalized in ADR-003):

```json
{
  "protocol": "time_aware",
  "created": "ISO-8601",
  "source_config": "configs/<experiment>.yaml",
  "config_hash": "...",
  "families": {"train": [...], "val": [...], "test": [...]},
  "hashes": {"train": ["<sha256>"], "val": ["..."], "test": ["..."]}
}
```

Leakage invariants (tested in `tests/unit/test_splits.py`, P1):

- no cluster crosses splits,
- train dates < validation dates < test dates (time-aware),
- fixed seed + same input ⇒ identical split.
