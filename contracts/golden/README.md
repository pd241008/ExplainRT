# contracts/golden/ — Golden fixtures and expected canonical text

This directory holds golden fixtures and expected canonical text for the polyglot
pipeline defined in [ADR-011](docs/adrs/adr-011-polyglot-architecture.md) (rev 4).

## What lives here

- Golden input fixtures for contract tests and leak-audit tests. Synthetic only;
  never real malware.
- Expected canonical text for each cross-language artifact, so Go, C++, Rust, and
  Python render the same message to the same text and therefore the same SHA-256.

## Rules

- Canonical text is the recorded artifact hash, not protobuf wire bytes.
- Golden fixtures are updated only when the contract or producer mapping changes
  through an ADR.
- Tests never need real malware.
