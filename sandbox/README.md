# Sandbox — Safe Malware Handling Boundary

The sandbox is the **only** environment where a malware sample may be executed,
imported, or behaviorally probed. This implements hard rule AGENTS.md §2 and
ADR-006. On the host, the only permitted interaction with a raw sample is
read-only parsing with `pefile`.

## Rules

1. **No network, ever.** Run with `--network none` (and keep the image
   install-free at run time). Network access from the sandbox is a
   stop-and-ask-the-human incident (AGENTS.md §9).
2. **Raw data is read-only.** `datasets/raw/` mounts as `:ro`. The immutable
   source can never be modified from a session.
3. **Ephemeral outputs.** Anything a session writes goes to
   `sandbox/workspace/` (gitignored) or to
   `datasets/processed/adversarial/`, and is deleted after evaluation.
4. **Never commit samples or derived binaries.** Commit hashes, split lists,
   and run records only.
5. **Sessions are logged.** Each session records purpose, command, snapshot
   ID, and output hashes into a `logger/` run record.

## Usage

```bash
docker build -t bytelens-sandbox sandbox/

docker run --rm --network none --memory 4g --cpus 2 \
  -v "$PWD/datasets/raw:/data:ro" \
  -v "$PWD/sandbox/workspace:/work" \
  bytelens-sandbox python3 - <<'PY'
import pefile
pe = pefile.PE("/data/<sample>")   # read-only parse inside the sandbox
print(len(pe.sections))
PY
```

## Snapshot discipline

Revert the VM/container to a clean snapshot between sessions with untrusted
input. A session that touches an unverified or crashed sample must not carry
state into the next one.

## If something goes wrong

- Unexpected network attempt, sample crash, or AV flag on the host:
  stop, keep the logs, revert the snapshot, and open a postmortem under
  `docs/postmortems/` (registry in `docs/postmortems/README.md`).
- Any proposed relaxation of these rules needs a new ADR first (AGENTS.md §9).
