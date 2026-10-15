# contracts/parquet/ — Pinned column schemas for bulk tables

This directory holds Parquet column-schema metadata for the bulk tables in the
polyglot pipeline defined in
[ADR-011](docs/adrs/adr-011-polyglot-architecture.md) (rev 4).

## What is Parquet here

- `sample_table` — per-sample rows produced by Go ingest: sha256 identity, size,
  and whatever metadata the dataset provides. The exact columns are provisional
  until the BODMAS metadata is confirmed present (ADR-011 risks 2).
- `region_table` — canonical PE region partition (ADR-001), produced by Rust
  peparse. Every byte gets exactly one region on valid synthetic fixtures.
- `instruction_boundaries` — optional decoder output (gated at G4).

## Rules

- Bulk tables are Parquet, not protobuf.
- Column schemas are pinned here so the Python side and the gate agree on shape.
- Column names must not encode raw sample paths or raw bytes; sample identity is
  sha256 only.
- Edit column schemas only via an ADR-approved change.
