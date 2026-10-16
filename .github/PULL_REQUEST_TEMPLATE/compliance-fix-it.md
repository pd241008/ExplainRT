## How to request a compliance or fix-it change

Thanks for keeping the repo auditable. For a compliance or fix-it PR, please keep it small and self-contained, and make the request explicit.

### Scope first
- One concern per PR.
- State what is non-compliant or broken, where it lives, and what the fix should do.
- If the fix changes a contract, ADR, dataset handling rule, or sandbox rule, say so up front.

### Compliance checklist
- [ ] The change traces to a rule in `AGENTS.md`, an ADR in `docs/adrs/`, or a contract in `contracts/`.
- [ ] No file path indicates real sample execution outside `sandbox/`. Malware-safety rule: never execute or import a sample outside the sandbox (ADR-006).
- [ ] `datasets/raw/` stays immutable and gitignored. No raw archive is edited, renamed, or committed.
- [ ] No binaries, packed samples, or generated adversarial PEs are committed. Only hashes, manifests, and split lists may be committed.
- [ ] If a number, metric, or threshold is introduced, it has a run record in `logger/` and a config + seed. No fabricated or estimated results (research-integrity rule).
- [ ] If the change touches a cross-language contract, it is an ADR-approved change, not a local tweak (ADR-011).

### Documentation
- If this PR changes behavior, update the relevant ADR, contract, or SOP — especially `datasets/raw/README.md` for ingest changes.
- If this is a fix-it PR, include the before/after in the body or in a tracked artifact, not only in the diff.
- If a new rule is added, note where it lives and what it replaces or supplements.

### Commits and authorship
- Use conventional commits: `type(scope): subject`.
- One logical change per commit where practical.
- **No `Co-Authored-By:` trailers.** This repo does not use co-author footers.
- Do not commit secrets, API keys, or anything that should be in an env file.

### Test surface
- Add or update tests for the changed behavior if one exists.
- Prefer tests that do not need real malware; use synthetic or benign PEs when possible.
- If the PR touches the smoke path, rerun `ruff check`, `ruff format --check`, and `pytest` before requesting review.

### When to stop and ask
- Dataset access, licensing, or timestamps are unclear or missing.
- Any step would execute a sample or touch the network from the sandbox.
- The collapse guard fails, an adaptive attack defeats a defense, or results contradict a paper claim.
- You want to add scope: new dataset, model, attack, or defense.

### After the PR
- Update `CHANGELOG.md` if the change is user- or researcher-facing.
- If the change opens or closes a gate condition, note it in the PR body.


