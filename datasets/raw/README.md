# datasets/raw/ — Immutable Source Data

**Status: EMPTY until data access is granted. AGENTS.md §9: stop and ask a
human when dataset access, licensing, or timestamps are unclear.**

Rules (hard rules, AGENTS.md §2):

- This directory is **immutable and gitignored**. Never edit, rename, or
  "fix" a raw file.
- Never execute, import, or "just try" a sample outside `sandbox/`.
  Parsing with `pefile` on the host is allowed only for files here, read-only.
- Never commit sample binaries. Commit SHA-256 hashes and split lists only.

Expected first dataset (primary scope): **BODMAS** — obtained from the owners
(`https://whyisyoung.github.io/BODMAS/`). Before ingestion, record in a tracked
file next to the data (not committed into git history as binaries):

- source URL / download date
- license / terms of use
- SHA-256 of every downloaded archive
- label taxonomy version and timestamp coverage (BODMAS provides timestamps —
  required for the time-aware split, ADR-003)
