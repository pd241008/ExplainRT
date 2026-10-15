# ADR-011 (rev 4): Polyglot architecture (Go ingest, C++ gate, Rust peparse, optional decode, Python) and mixed proto + JSON + Parquet contracts

- **Status:** Proposed (revision 4; replaces rev 3 of 2026-10-15)
- **Date:** 2026-10-15
- **Amends:** AGENTS.md section 4 (repo layout) and the "Python only" assumption; depends on ADR-001 (regions), ADR-002 (shared resize), ADR-006 (sandbox), ADR-007/009 (run records, provenance), ADR-008 (datasets)

## Context

BODMAS binaries are available as a **67 GB zip** that expands to roughly **300 GB**
of unpacked PE binaries on an **external hard disk**. The owner wants to reuse parts
of Helios (Go ingestion, evidence-first workflow) and Byteweaver (x86-64 decoder),
and wants C++ to act as the **abstraction and contract enforcer**: it manages the
stage contracts and makes sure no binary is ever executed by accident. This revision
keeps C++ as the gate, adds the external-drive verify-first read-only raw discipline,
and adopts mixed contracts: protobuf for cross-language control-plane artifacts, JSON
Schema for JSON artifacts, and Parquet column schemas for bulk tables.

Sample count and the exact manifest/sample-table shape are **not confirmed** until the
BODMAS metadata is present on the working machine; the pipeline contract must stay
provisional on those fields until then.

Not reused: Spark/Sedona (the data is independent files, not 25.8M spatial rows).

## Decision

### 1. Raw data is an external immutable store; verify first, then derive

```
external drive (raw BODMAS bundle)
   |  zip is the entry artifact: verify its SHA-256 first
   |  then unzip into a controlled RW derived/workspace area
   v
unpacked PE tree is treated as **derived-from-zip raw**, still read-only
   |  no in-place edits, renames, or "fixes"
```

- The external drive is the immutable source of truth for raw binaries.
- The raw/PE-visible side is mounted **read-only** for any stage that sees samples.
  Write access is allowed only for derived/scratch output, never back onto the raw
  tree.
- If the unpacked 300 GB tree already exists on the drive, treat it as
  derived-from-zip raw and keep it read-only. Never edit, rename, or "fix" a raw
  file in place. This is the same rule already in AGENTS.md §2 and
  `datasets/raw/README.md`, now applied to the external drive.
- The host never executes, imports, or "just tries" a sample. Host interaction with
  raw binaries is read-only `pefile` parsing only (ADR-006). Anything
  execution-shaped stays in `sandbox/`.

### 2. Domains and roots (physically separate, one build tool each)

```
ingest/      Go      go.mod, go.sum          zip hash verify, unzip control,
                                            per-file SHA-256, manifest, sample table
gate/        C++     CMakeLists.txt          contract enforcer, sample broker,
                                            no-exec preflight, disarm check,
                                            adversarial output guard, audit log
peparse/     Rust    Cargo.toml, Cargo.lock  PE parse, region partition,
                                            validity checker
decode/      (opt.)  Byteweaver              instruction boundaries; optional,
                                            gated (G4)
bytelens/    Python  requirements.txt        everything numeric (existing package)
contracts/   shared by all domains:
  proto/       protobuf IDL for cross-language control-plane artifacts (package explainrt.contracts.v1)
  schema/      JSON Schema for JSON artifacts (manifest, split locks, run-record lines, freeze locks)
  parquet/     pinned column schemas for bulk tables (sample table, region table)
  producers.json   fact -> producing stage -> artifact format (policy map, not a data schema)
  rules.json   per-artifact gate rules (required fields, sha256 pattern, forbidden names, string caps)
  golden/      golden fixtures and expected canonical text, one set for all four languages
  gen/         generated protobuf code per language, committed (see section 8.5)
logger/ runner/ configs/ docs/ paper/        unchanged (root-level, Python)
```

No mixed build files across domains; each has its own README, pinned toolchain, and
CI job.

### 3. Responsibilities

| Domain | Does | Does NOT do |
|---|---|---|
| Go `ingest/` | Verify the zip SHA-256; control the unzip into RW derived space; SHA-256 every file; join to metadata by sha256; write manifest entries and the sample table | Parse PEs; open samples for any other stage |
| **C++ `gate/`** | Validate every stage input and output against `contracts/`; enforce one producer per fact; be the **only component that opens sample files** and serve them by SHA-256 ID; run the no-execution preflight; check samples and generated files for the disarmed state; write the access audit log | Parse PEs beyond fixed-offset header checks; render; model; compute any result |
| Rust `peparse/` | Parse each PE defensively; canonical region table; structural validity of generated PEs. Runs only under the gate's sandbox profile | Open sample paths itself; write contracts it does not own |
| Python `bytelens/` | Differentiable resize, render, features, models, Grad-CAM, attacks, defenses, stats, run records (sole writer of the hash chain) | Re-derive hashes, regions, or boundaries; open sample paths itself |

**One source of truth per fact:** hashes (Go), regions (Rust), instruction
boundaries (decode, if used), everything else (Python). The gate does not produce
facts; it **checks** that the right stage produced them and that they satisfy the
contract.

### 4. Gate behavior

**G-1 Contract enforcement.**
- Every stage report and output file is validated against its authoritative
  definition (proto message, JSON Schema, or Parquet column schema, as listed in
  `producers.json`): required `schema_version`, tool version, git SHA, input hashes
  and recomputed output hash; sorted deterministic rows; **forbidden fields** (file
  paths, raw bytes) rejected.
- `contracts/producers.json` maps each fact (sample ID, region table, instruction
  boundaries, run record) to its single producing stage **and** its artifact format.
  An output from any other stage is rejected.
- **Fail closed:** unknown schema versions, **unknown protobuf fields**, unknown JSON
  keys, and unknown Parquet columns are rejected. Protobuf's own compatibility rules
  tolerate unknown fields, so the gate checks for them explicitly; stages must not
  consume any artifact the gate has not validated.

**G-2 Sample broker.**
- Stages never see sample paths. They request bytes by SHA-256 ID; the gate checks
  the ID is in the manifest, verifies the file hash on first open (cached), and
  passes a read-only buffer (read-only `mmap`, never `PROT_EXEC`) over a file
  descriptor or pipe to the sandboxed stage.
- Requests for IDs not in the manifest, or whose hash does not match, are refused.

**G-3 No-execution preflight (fail closed, every run).**
- The data root is mounted `ro,noexec,nodev,nosuid`; no sample has any execute bit;
  no symlink or hard link leaves the root; the process is unprivileged.
- The sandbox has no network interface with a route.
- A seccomp profile is loaded before any parsing: deny `execve` and `execveat`,
  deny creating new processes (threads only), deny `mmap` and `mprotect` with
  `PROT_EXEC`, deny sockets.
- **Canary self-test:** inside the sandbox profile the gate tries to `execve` a
  harmless known file and to map memory executable, and requires both to fail. If
  either succeeds, the run is aborted.

**G-4 Disarm check.**
- Before serving a sample, check fixed-offset header fields only (DOS magic,
  `e_lfanew` within bounds, `FileHeader.Machine`, `OptionalHeader.Subsystem`)
  against the disarmed state described in the BODMAS and SOREL-20M documentation.
  **The exact fields and values are not chosen here.** They must be verified against
  the dataset documentation and its restore script before G1 is written (read only,
  never run). A sample that looks armed is refused and its hash is logged.
- **Adversarial output guard:** generated files are written only to
  `datasets/processed/adversarial/`, only through the gate, and only in the disarmed
  state; a file whose header looks executable is refused. Generated files are deleted
  after evaluation.
- The `--arm` restore is never run on the host; any execution experiment is
  sandbox-only and named in its own ADR.

**G-5 Audit log.** The gate writes a JSONL log of every decision (SHA-256, stage,
allow or deny, reason, time). Its hash is recorded in the run record. No paths, no
bytes.

### 5. Gate constraints (C++ is memory-unsafe, so keep it small)

- Fixed-offset, bounds-checked header reads only; no general PE parsing (that stays
  in Rust).
- No `system`, `popen`, or `exec*` anywhere in `gate/` except one allowlisted
  launcher for our own pinned stage binaries; a CI check greps for the others.
- Minimal pinned dependencies (a JSON and JSON-schema library, libseccomp); no
  dynamic loading.
- Hardened build (`-fstack-protector-strong`, `-D_FORTIFY_SOURCE=2`, PIE, RELRO);
  ASan and UBSan in CI; libFuzzer on the header checks and the schema loader, using
  synthetic malformed inputs only.

### 6. Storage and working-set numbers (updated for the 300 GB bundle)

- Entry artifact: **67 GB zip** on the external drive.
- Unpacked raw: **roughly 300 GB** of PE binaries.
- Peak working set: zip + derived artifacts (manifest, sample table, regions,
  renders, adversarial output). The exact peak depends on which derived stages are
  materialized at once.
- Delete the zip only after its hash is verified and the derived manifest is written,
  if storage pressure requires it. The unpacked raw tree remains the immutable store
either way.

### 7. Data flow

```
67 GB BODMAS zip (external drive, read-only raw store)
   |  Go ingest: verify zip hash, control unzip into RW derived space,
   |  hash each file, join metadata
   v
MANIFEST.json + samples.parquet
   |  C++ gate: preflight, contract check, serve bytes by ID (sandboxed)
   v
Rust peparse  ->  regions.parquet + parse_report.proto     (checked by the gate)
   |
   v
Python: render, features, train, explain, attack, defend, evaluate
   |  generated PEs written only through the gate (disarmed state)
   v
logger/ run records (hash chain)  ->  paper/ tables and figures
```

### 8. Interface contract (mixed protobuf, JSON, Parquet)

- Files and file descriptors only: no FFI, no network between stages. Outputs
  deterministic. Sample IDs are SHA-256 only. Paths come from configuration or
  `EXPLAINRT_DATA_ROOT`, never hard-coded.
- Python's `logger/` is the only writer of the run-record hash chain; stage and gate
  reports are referenced by SHA-256.

**8.1 Which format for which artifact.** Each artifact has exactly one authoritative
definition; no artifact is defined twice.

| Artifact | Format | Why |
|---|---|---|
| Stage report, parse report, gate decision (audit) record, sample reference, run-record reference | **Protobuf** (`contracts/proto/`) | Small control-plane messages that cross Go, C++, Rust, and Python |
| `MANIFEST.json`, split lock files, freeze locks, run-record lines (JSONL), configs | **JSON** (+ JSON Schema) | Human-read, git-diffed, already produced and consumed by the Python logger tooling |
| Sample table, region table, instruction boundaries (bulk rows) | **Parquet** (pinned column schema) | Tens of thousands of rows; columnar, efficient for Python |

Protobuf messages are not used for bulk tables. Messages that appear on a JSON edge
(for example a run-record reference inside a JSONL line) use the JSON form defined in
8.3.

**8.2 Versioning (two layers).**
- *Wire layer:* protobuf package `explainrt.contracts.v1`. Within v1 only additive,
  optional fields are allowed; field numbers and names are never reused (`reserved`);
  a breaking change creates package `v2`. No `required`, no `oneof` reuse of numbers,
  no `map` fields (unordered), and no floating-point fields in contract messages (use
  integers or decimal strings), so canonical text is stable.
- *Artifact layer:* every artifact (proto, JSON, Parquet metadata) carries
  `schema_version = "MAJOR.MINOR"`. MAJOR equals the proto package version (or the
  JSON Schema major); MINOR increments on each additive field. The gate accepts an
  artifact only if MAJOR equals its own and MINOR is no greater than the MINOR it
  supports; a newer MINOR is rejected until the gate is upgraded. Both versions are
  recorded in the stage report.

**8.3 Hashing and determinism.** The recorded hash of any artifact is taken over its
**canonical text form**, never over protobuf wire bytes (wire encoding is not
guaranteed byte-identical across languages and library versions). Canonical text: JSON
with sorted keys, UTF-8, no extra whitespace, integers and decimal strings only (the
`canonical_json` rule of ADR-009); a protobuf message is rendered to this form with
fields ordered by field number, all fields emitted including defaults, and int64 as
decimal strings. One shared renderer rule, tested by golden fixtures in all four
languages (identical canonical text and identical SHA-256).

**8.4 Leak-audit rules (enforced twice).**
- *CI lint on the IDL and schemas:* no `bytes` fields; no field named like a path,
  file, or content; sample identity is a `sha256` field only.
- *Runtime in the gate (`rules.json`):* `sha256` fields match
  `^[0-9a-f]{64}$, string fields are length-capped and may not contain path
  separators unless the rule marks them as a URL, unknown fields are rejected, and any
  message violating these is refused and logged by hash.

**8.5 Toolchain.** A pinned `protoc` (or `buf`) with pinned language plugins generates
code for Go, C++, Rust, and Python. **Generated code is committed under
`contracts/gen/`, and CI regenerates it and fails on any diff.** This keeps "one build
tool per domain": each domain builds from the committed generated code with its own
tool and never needs `protoc`. Regeneration is a separate, explicit step
(`contracts/` owns it).

### 9. Reuse from Helios and Byteweaver

- Each imported module is listed in `docs/reuse.md` (source, commit SHA, licence,
  changes, date) and must pass this repo's golden tests first.
- Helios workflow adopted: five-part evidence bundle per reported result, owner-kept
  tracker, agents execute and report, explicit task boundaries, and the WSL2 gotchas
  (check `df -h` on target paths, `rsync` trailing slashes, scratch off the drvfs
  boundary, do not extract 151 GB inside a WSL2 virtual disk).
- **Byteweaver decoder:** optional `decode/` module, gated at G4. Implementation (C++
  or Rust, with the other as differential-test oracle against `objdump`) is chosen when
  G4 opens, not now.

### 10. Phases and gates

| Gate | Deliverable | Pass condition |
|---|---|---|
| G0 | Go ingest | Zip hash verified; per-file SHA-256 equals the metadata sha256 for all samples; `verify-data` passes; Go hash equals Python `hashlib` on fixtures |
| **G1** | **C++ gate** | All gate tests below pass in CI; canary self-test passes in the real sandbox; fuzzing finds no crash on the header checks |
| G2 | Rust peparse (runs only via the gate) | Every byte gets exactly one region on synthetic PEs; renamed-section fixtures correct; BODMAS parse-failure rate reported |
| G3 | Python render and baselines | Shared resize (ADR-002); baselines on the 10% subset with real run records |
| G4 (decision) | Optional decoder | Decode success rate measured and reported; the threshold is written in an ADR before the measurement |
| Week-6 gate | Unchanged | Human go/no-go, TIFS vs Computers & Security |

### 11. Gate tests (synthetic fixtures only)

1. Canary: `execve` inside the sandbox profile fails (`EPERM`).
2. `mmap` or `mprotect` with `PROT_EXEC` is denied.
3. A fixture with an execute bit is refused.
4. A symlink or hard link leaving the data root is refused.
5. A synthetic header that looks armed is refused; a synthetic disarmed header is
   served.
6. An ID not in the manifest is refused; a hash mismatch is refused.
7. A stage output from the wrong producer is rejected.
8. A report with an unknown field, a missing hash, or a path field is rejected.
9. An unknown `schema_version` fails closed.
10. A generated file with an executable-looking header is refused by the output guard.
11. A protobuf message with an unknown field is rejected (even though protobuf itself
    would accept it).
12. Golden canonical-text test: the same message renders to identical text and SHA-256
    in Go, C++, Rust, and Python; a message with a float or map field fails the IDL
    lint.
13. IDL lint rejects a `bytes` field and a path-like field name; a message with a path
    separator in a string field is refused at runtime.
14. A stage report with a newer MINOR than the gate supports is rejected; a different
    MAJOR is rejected.
15. CI regeneration check: regenerated code differs from `contracts/gen/` and the
    build fails.

## Alternatives considered

- **Gate in Rust instead of C++:** safer for hostile input and the better engineering
  default. Kept as the fallback if C++ memory safety becomes a burden; C++ was chosen
  by the owner and is bounded by section 5.
- **Python-only enforcement:** simplest, but the enforcing code would sit in the same
  process as the numeric code it polices. Rejected.
- **Enforcement by documentation and review only:** not fail-closed. Rejected.
- **FFI or services (PyO3, gRPC):** more moving parts and couples build systems.
  Rejected.
- **JSON Schema only:** simplest toolchain and canonical hashing for free, but weaker
  typed code per language. Rejected for cross-language artifacts by the owner in favor
  of proto; kept for JSON artifacts.
- **Protobuf for everything, including bulk tables and logger JSON:** bulk tables belong
  in Parquet, and the logger and split tooling already speak JSONL. Rejected.
- **Spark/Sedona:** wrong scale. Rejected.

## Consequences

- One choke point for sample access and contracts: easy to audit, and the paper can
  state it precisely.
- **The gate is a policy layer, not the security boundary.** The boundary is the OS:
  read-only noexec mount, seccomp, no network, an unprivileged user, ideally a VM. The
  gate makes those controls mandatory and checks them every run; it cannot protect a host
  where they are missing.
- Raw binaries now live on an external drive with a verify-first, read-only raw
  discipline. That closes the biggest leak path for a 300 GB bundle: no stage gets raw
  paths, the zip hash is verified before anything is derived, and write access is
  confined to derived/scratch output.
- A small amount of memory-unsafe code now sits on the sample path; section 5 limits it
  to header checks and fuzzes it.
- Four toolchains in CI (five if the decoder is used); slower onboarding. Contracts add
  a code-generation step, controlled by committing generated code and diffing in CI.
- The gate links the protobuf C++ runtime, a larger dependency on the sample path than a
  JSON library; pin it, fuzz message parsing, and decide full versus lite runtime when G1
  starts (the unknown-field rejection test, test 11, must pass either way).
- Three definition formats (proto, JSON Schema, Parquet schema) require the registry in
  `producers.json` to stay accurate; a contract with two definitions is a defect.
- The paper's architecture description, Fig. 2, and supplement Appendix C must be
  updated (C++ is the gate, the decoder is optional, contracts are mixed proto + JSON +
  Parquet).

## Risks and open questions

1. **Disarmed-state field values are not locked.** They must be verified against the
   dataset documentation before G1 is written (read the restore script, never run it).
   **Blocks G1.**
2. **Sample count and manifest/sample-table shape are not confirmed.** The BODMAS
   metadata files are not yet confirmed present on the working machine; the manifest and
   sample-table shape stay provisional until we know which fields the dataset actually
   provides. **Blocks G0.**
3. Seccomp and namespaces depend on the kernel and WSL2 configuration; if unavailable,
   run the sandbox in a VM or container and record the limitation.
4. Terms of use: only hashes, split lists, metrics and run records are ever published.
5. The external drive is an immutable store by policy and by mount discipline; if the
   drive or mount cannot be made reliably read-only for the sample path, that is a
   stop-and-ask item (AGENTS.md §9), not a silent relaxation.

## Revisit When

- G1 canary or fuzzing shows the gate cannot be made reliable in C++ (move it to Rust).
- Canonical text differs across languages in practice, or schemas drift between proto and
  JSON edges (reconsider the split, or collapse the JSON edges into one format).
- Generated-code churn or the protobuf C++ runtime proves too heavy for the gate.
- Seccomp or `noexec` cannot be enforced in the working environment.
- The disarm method or BODMAS terms change.
- G4 opens (choose the decoder implementation).
- Cross-language CI cost slows work noticeably.
- The external drive cannot be mounted read-only for the raw sample path, or the
  zip-verify-first step cannot be enforced (then pause and record the limitation).
