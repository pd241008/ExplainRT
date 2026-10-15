# peparse/ — Rust PE parse stage

This directory is the Rust PE parse stage for the polyglot pipeline defined in
[ADR-011](docs/adrs/adr-011-polyglot-architecture.md) (rev 4).

## Responsibility

- Parse each PE defensively.
- Produce the canonical region table.
- Produce the structural validity report for generated PEs.

## Build tool

Rust with Cargo. This directory has its own `Cargo.toml` and is built
independently of the other domains. No mixed build files across domains.

## Contract

Parse report is a protobuf message (`contracts/proto/parse_report.proto`).
Region table is bulk Parquet with a pinned column schema
(`contracts/parquet/region_table.json`) plus a protobuf reference
(`contracts/proto/region_table.proto`). The fact-to-stage-to-format registry is
`contracts/producers.json`.

## Safety

- Runs only under the gate's sandbox profile.
- Does not open sample paths itself; receives bytes from the gate.
- Does not write contracts it does not own.

## Current state

Scaffold. Compilable placeholder until G2.
