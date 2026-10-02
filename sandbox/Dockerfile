# ByteLens sandbox image — the ONLY place a sample may ever be executed,
# imported, or behaviorally probed (hard rule, AGENTS.md §2).
#
# Build:   docker build -t bytelens-sandbox sandbox/
# Run:     docker run --rm --network none --memory 4g --cpus 2 \
#             -v "$PWD/datasets/raw:/data:ro" -v "$PWD/sandbox/workspace:/work" \
#             bytelens-sandbox <command>
#
# The --network none flag is mandatory: the sandbox has no network by design.
# datasets/raw is mounted read-only, so no run can mutate the immutable source
# data (AGENTS.md §2). Nothing sample-related is baked into the image; the
# image is tooling only (python + pefile), which keeps rebuilds clean.

FROM python:3.12-slim

# Tooling only. Install happens at build time, never at run time: combined
# with --network none this makes network access from a session impossible.
RUN pip install --no-cache-dir pefile==2024.8.26

# Non-root user inside the container; workspace and mounts are writable only
# through the mounted volume.
RUN useradd --create-home --shell /bin/bash analyst
USER analyst
WORKDIR /work

# No CMD: sessions are explicit, one command per run, container removed after.
