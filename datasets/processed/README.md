# datasets/processed/ — Derived Data

Regenerable artifacts produced by `bytelens/` code from `datasets/raw/`:
parsed PE metadata, features, renders. Everything here is derived and
gitignored. Regenerate from raw + a config; do not hand-edit.

## Layout (created by pipeline code)

```
datasets/processed/
├── pe_metadata/       # pefile parse results, one record per sample
├── features/          # LightGBM feature tables
└── renders/           # binary -> image renders (ADR-002 resize)
```

## adversarial/ — Ephemeral

Generated adversarial PEs (attacks A1–A8) are written **only** here and are
**deleted after evaluation** unless a human says otherwise (hard rule,
AGENTS.md §2). Never commit anything in this subtree. Keep a hash list of
generated files in the run record, not the files themselves.
