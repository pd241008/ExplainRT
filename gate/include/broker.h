// gate/include/broker.h
//
// Sample broker and contract-enforcement header for the C++ gate stage.
//
// This is the top-level interface the gate exposes to the rest of the pipeline
// defined in ADR-011 (rev 4). The gate is the only component that opens sample
// files and serves bytes by SHA-256 ID. Stages never see sample paths.
//
// This file is a scaffold. It compiles as a placeholder until G1 work starts.

#ifndef GATE_BROKER_H
#define GATE_BROKER_H

#include <cstdint>
#include <string>

namespace gate {

struct SampleRequest {
  std::string sha256; // hex-encoded, 64 chars
};

struct SampleHandle {
  // Opaque read-only handle to sample bytes. Implementation may use mmap,
  // pipe, or file descriptor. Never PROT_EXEC.
};

// Called once per sample request. Returns a handle only if the ID is in the
// manifest, the file hash matches, and the disarmed-state header check passes.
// Otherwise the request is refused and logged by hash.
SampleHandle serve_by_id(SampleRequest request);

// Returns true if the request was allowed.
bool request_allowed(const SampleRequest& request);

} // namespace gate

#endif // GATE_BROKER_H
