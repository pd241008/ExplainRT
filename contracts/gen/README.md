# contracts/gen/ — Generated protobuf code (committed)

Generated protobuf code for Go, C++, Rust, and Python lives here and is committed.
Each domain builds from this committed generated code and never needs `protoc` at
build time (ADR-011 8.5).

## Rules

- CI regenerates this directory from `proto/` and fails on any diff.
- Do not edit generated code by hand.
- Regeneration is a separate, explicit step owned by `contracts/`.
