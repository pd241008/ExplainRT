# contracts/schema/ — JSON Schema for JSON artifacts

This directory holds JSON Schemas for the JSON artifacts in the polyglot pipeline
defined in [ADR-011](docs/adrs/adr-011-polyglot-architecture.md) (rev 4).

## What is JSON here

- `MANIFEST.json` — Go ingest output (dataset identity, zip sha256, per-file
  sha256 list with metadata joins). Metadata and hashes only; no data, no raw
  paths outside configuration.
- Split lock files, freeze locks, run-record lines (JSONL), and configs — these
  are already produced and consumed by the Python logger/runner tooling.
- Run-record references that appear inside JSONL lines use `schema/run_record_ref.json`.

## What is NOT JSON here

- Parse report and region table moved to proto/Parquet in rev 4. This directory no
  longer defines them.
- Bulk tables are Parquet, with column schemas in `parquet/`.

## Rules

- Unknown keys fail closed. Forbidden fields (file paths, raw bytes) fail closed.
- Sample identity is a `sha256` field only.
- Edit schemas only via an ADR-approved change.
