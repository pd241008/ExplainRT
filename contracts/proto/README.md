# contracts/proto/ — Protobuf IDL for cross-language control-plane artifacts

This directory holds the protobuf IDL for the small control-plane messages that
cross Go, C++, Rust, and Python in the polyglot pipeline defined in
[ADR-011](docs/adrs/adr-011-polyglot-architecture.md) (rev 4).

## Package and versioning

- Package: `explainrt.contracts.v1`.
- Within v1 only additive, optional fields are allowed. Field numbers and names
  are never reused (`reserved`). A breaking change creates package `v2`.
- No `required`, no `oneof` reuse of numbers, no `map` fields (unordered), and no
  floating-point fields in contract messages. Use integers or decimal strings so
  canonical text is stable.

## Leak-audit constraints (also enforced in CI and in the gate)

- No `bytes` fields.
- No field named like a path, file, or content.
- Sample identity is a `sha256` field only.

## Files

- `manifest.proto` — sample manifest control-plane message (Go ingest output).
- `parse_report.proto` — PE parse report (Rust peparse output).
- `region_table.proto` — canonical region-table reference (Rust peparse output).
- `run_record_ref.proto` — run-record reference shape used by the gate and stages.

## Generated code

Generated code is committed under `contracts/gen/` and is the source each domain
builds from. CI regenerates it and fails on any diff (ADR-011 8.5). Do not edit
generated code by hand.
