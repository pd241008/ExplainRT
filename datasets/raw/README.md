# datasets/raw/ — Immutable Source Data

**Status: READY FOR INGEST. bodmas folder on the attached disk contains the dataset archives; load it into this directory per the SOP below. AGENTS.md §9: stop and ask a
human when dataset access, licensing, or timestamps are unclear.**

Rules (hard rules, AGENTS.md §2):

- This directory is **immutable and gitignored**. Never edit, rename, or
  "fix" a raw file.
- Never execute, import, or "just try" a sample outside `sandbox/`.
  Parsing with `pefile` on the host is allowed only for files here, read-only.
- Never commit sample binaries. Commit SHA-256 hashes and split lists only.

Expected first dataset (primary scope): **BODMAS** — obtained from the owners
(`https://whyisyoung.github.io/BODMAS/`).### Ingest SOP (run from the raw-store machine, never from a sample-hosting host)

1. **Confirm the disk image mount and that no binary will be executed on this host.**
   - The attached disk holds the `bodmas/` folder containing the dataset archives.
   - Keep binaries disarmed on this host: mount read-only, or copy to a quarantine subfolder and work only from there; do not mount execute permissions if the OS allows it.
   - Nothing in `bodmas/` is ever executed, imported, or "tried" on this host. Parsing with `pefile` (read-only) is allowed only for files after they have been placed in `datasets/raw/` and only for metadata we need for the ingest manifest.

2. **Copy archives into `datasets/raw/`** (this directory is gitignored; the copy is the immutable raw store).
   - Preserve the source folder timestamps where the archive format allows it; they matter for ADR-003 time-aware splits.
   - Do not rename or "fix" any archive. If an archive is corrupted, stop and log it; do not patch it.

3. **Record provenance in the tracked file next to the data** (`datasets/raw/BODMAS-INGEST.json`), not in git history as binaries:
   - source URL / download date
   - license / terms of use
   - SHA-256 of every downloaded archive
   - label taxonomy version and timestamp coverage (BODMAS provides timestamps — required for the time-aware split, ADR-003)

4. **Run the Python ingest manifest builder** (module 3 below) against the placed archives.
   - That step only reads archives and writes metadata; it never executes a sample.

5. **After ingest, verify the manifest** with the existing smoke path before any sample touches the sandbox.
   - The existing end-to-end smoke uses `datasets/raw/bodmas.npz`, not live PEs; keep that as the no-sample integration check until the new MANIFEST.json + sample table are in place.
