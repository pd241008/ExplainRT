# ingest/ — Go ingest stage

This directory is the Go ingest stage for the polyglot pipeline defined in
[ADR-011](docs/adrs/adr-011-polyglot-architecture.md) (rev 4).

## Responsibility

- Verify the BODMAS zip SHA-256.
- Control the unzip into a controlled RW derived area.
- SHA-256 every file.
- Join metadata by sha256.
- Write the manifest and the sample table.

## Build tool

Go. This directory has its own `go.mod` and is built independently of the other
domains. No mixed build files across domains.

## Contract

Ingest output is a JSON artifact (`MANIFEST.json`) plus a Parquet sample table.
The authoritative definitions are in `contracts/schema/manifest.json` and
`contracts/parquet/sample_table.json`. The fact-to-stage-to-format registry is
`contracts/producers.json`.

## Safety

- Raw binaries are never opened by this stage for any other stage.
- No sample bytes are written into contract artifacts.
- Sample identity is SHA-256 only.
