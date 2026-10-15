# gate/ — C++ contract enforcer and sample broker

This directory is the C++ gate stage for the polyglot pipeline defined in
[ADR-011](docs/adrs/adr-011-polyglot-architecture.md) (rev 4).

## Responsibility

- Validate every stage input and output against `contracts/`.
- Enforce one producer per fact (from `contracts/producers.json`).
- Be the only component that opens sample files and serve them by SHA-256 ID.
- Run the no-execution preflight.
- Check samples and generated files for the disarmed state.
- Write the access audit log.

## Build tool

C++ with CMake. This directory has its own `CMakeLists.txt` and is built
independently of the other domains. No mixed build files across domains.

## Contract

Gate inputs and outputs are validated against the authoritative definitions
listed in `contracts/producers.json`. Cross-language control-plane messages are
protobuf (`contracts/proto/`). JSON artifacts use `contracts/schema/`. Bulk-table
column schemas are in `contracts/parquet/`. Runtime reject rules are in
`contracts/rules/rules.json`.

## Safety constraints

- Fixed-offset, bounds-checked header reads only; no general PE parsing (that
  stays in Rust).
- No `system`, `popen`, or `exec*` except one allowlisted launcher for our own
  pinned stage binaries; CI greps for the others.
- Minimal pinned dependencies; no dynamic loading.
- Hardened build in CI; ASan/UBSan; fuzz the header checks and schema loader
  with synthetic malformed inputs only.

## Current state

Scaffold. Compilable placeholder until G1.
