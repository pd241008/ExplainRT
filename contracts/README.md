# contracts/ — Shared Interface Contracts for All Domains

This directory is the shared contract layer for the polyglot pipeline defined in
[ADR-011](docs/adrs/adr-011-polyglot-architecture.md) (rev 4).

## What lives here

- `proto/` — protobuf IDL for cross-language control-plane artifacts
  (package `explainrt.contracts.v1`): stage report, parse report, gate decision
  record, sample reference, run-record reference. No bulk tables.
- `schema/` — JSON Schema for JSON artifacts: `MANIFEST.json`, split lock files,
  freeze locks, run-record lines (JSONL), configs. Human-read, git-diffed.
- `parquet/` — pinned column schemas for bulk tables: sample table, region table,
  and any instruction-boundary bulk output. Parquet metadata only; no rows.
- `producers.json` — maps each pipeline fact to its single producing stage **and**
  its artifact format. The gate rejects outputs from any other stage (ADR-011 G-1).
- `rules.json` — per-artifact gate reject rules: required fields, sha256 pattern,
  forbidden field names, string length caps, path-separator rules. This is the
  runtime half of the leak-audit rules; the other half is IDL/Schema lint in CI.
- `golden/` — golden fixtures and expected canonical text, one set for all four
  languages. Synthetic only; never real malware.
- `gen/` — generated protobuf code per language, committed. Each domain builds
  from this; CI regenerates it and fails on any diff (ADR-011 8.5).

## Rules

- Each artifact has **exactly one authoritative definition**. No artifact is
  defined twice across proto, JSON Schema, and Parquet metadata. If a fact has two
  definitions, that is a defect, not a feature.
- Contracts are **checked, not proposed**, at run time. The gate validates every
  stage report and output file against the authoritative definition listed in
  `producers.json` for that fact.
- Unknown `schema_version` fails closed. Unknown protobuf fields fail closed
  (even though protobuf itself would accept them). Unknown JSON keys fail closed.
  Unknown Parquet columns fail closed. Forbidden fields (file paths, raw bytes)
  fail closed.
- One producer per fact. If a fact appears with a producer that is not the one in
  `producers.json`, the output is rejected.
- Sample identity is `sha256` only. No stage output carries raw sample bytes. No
  stage output carries raw sample paths except allowed configuration paths.
- Edit contracts only via an ADR-approved change. This is a shared dependency
  across Go, C++, Rust, and Python; a contract change is a cross-domain change, not
  a local tweak.

## Artifact format assignment

| Fact | Producer | Format | Authoritative definition |
|---|---|---|---|
| zip_sha256 | ingest | JSON | `schema/manifest.json` (embedded in MANIFEST.json) |
| sample_manifest | ingest | JSON | `schema/manifest.json` |
| per_file_sha256 | ingest | Parquet (bulk) / JSON (manifest) | `parquet/sample_table.json` + `schema/manifest.json` |
| sample_table | ingest | Parquet | `parquet/sample_table.json` |
| parse_report | peparse | Protobuf | `proto/parse_report.proto` |
| region_table | peparse | Parquet (bulk) / Protobuf (reference) | `parquet/region_table.json` + `proto/region_table.proto` |
| instruction_boundaries | decode | Parquet (bulk) | `parquet/instruction_boundaries.json` |
| render | bytelens | Python-side artifact | not a cross-language contract artifact |
| features | bytelens | Python-side artifact | not a cross-language contract artifact |
| model_artifact | bytelens | Python-side artifact | not a cross-language contract artifact |
| run_record | bytelens | JSONL (Python) + Protobuf refs | `schema/run_record_ref.json` + `proto/run_record_ref.proto` |

"Python-side artifact" means the artifact stays inside the Python pipeline and is
not a cross-language control-plane message. Those are still covered by the existing
Python contract discipline in `logger/` and `runner/`; they are not redefined here.

## Leak-audit rules (enforced twice)

- In CI, lint the IDL and schemas: no `bytes` fields; no field named like a path,
  file, or content; sample identity is a `sha256` field only.
- In the gate, enforce `rules.json`: `sha256` fields match
  `^[0-9a-f]{64}$`, string fields are length-capped and may not contain path
  separators unless the rule marks them as a URL, unknown fields are rejected, and
  any message violating these is refused and logged by hash.

## Test discipline

- Tests never need real malware. Use synthetic or benign PEs in `golden/` and in
  the domain test fixtures.
- The leak-audit suite verifies that no artifact carries raw sample bytes, no
  artifact carries raw sample paths except allowed configuration paths, and every
  artifact passes its schema/IDL/Parquet-metadata + producer check.
- Golden fixtures are the source of truth for "what a valid artifact looks like";
  they are updated only when the contract or producer mapping changes through an ADR.
- Canonical-text hashing is the recorded artifact hash, not protobuf wire bytes.
  Golden fixtures include the expected canonical text for each cross-language
  artifact so all four languages render identically.
