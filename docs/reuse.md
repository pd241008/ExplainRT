# Reuse — imported modules

This file is the registry for third-party modules reused in the polyglot pipeline
defined in [ADR-011](docs/adrs/adr-011-polyglot-architecture.md) (rev 4).

## Rule

Every imported module is listed here with source, commit SHA, licence, changes,
and date, and must pass this repo's golden tests first (ADR-011 9).

## Currently reused

None yet. The Helios ingestion workflow and the Byteweaver decoder are intended
reuse targets, but no code from them has been integrated into this repo yet.
When code is imported, add an entry here before it is used by any stage.

This file is the reuse registry. It is not the contract layer and not the gate
configuration; for runtime authority see `contracts/rules/rules.json` and
`contracts/producers.json`.

At present this registry is empty because the pipeline is being stood up to
receive real BODMAS archives from the attached disk. Ingestion begins only
after the disk is loaded into `datasets/raw/` and `datasets/raw/BODMAS-INGEST.json`
is written, per `datasets/raw/README.md` § Ingest SOP.
