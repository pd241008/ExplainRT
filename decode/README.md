# decode/ — optional Byteweaver instruction-boundary decoder

This directory is the optional decoder stage for the polyglot pipeline defined in
[ADR-011](docs/adrs/adr-011-polyglot-architecture.md) (rev 4).

## Status

Optional and gated at G4. Not started now.

## Responsibility

- Produce instruction boundaries for samples, if used.

## Build tool

Implementation (C++ or Rust, with the other as a differential-test oracle against
`objdump`) is chosen when G4 opens, not now. This directory is reserved.

## Contract

If used, bulk output is Parquet with a pinned column schema
(`contracts/parquet/instruction_boundaries.json`). The fact-to-stage-to-format
registry is `contracts/producers.json`.
