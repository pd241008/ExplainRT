"""PE-valid problem-space attacks A1-A8: append, inject-section, pad-slack editors.

Every attack is a **PE editor**: it mutates the file so the output stays a
structurally valid PE (still parses with ``pefile``), never alters original
bytes outside the declared edit region, and respects the perturbation budget
(Q bytes and epsilon * N fraction, both from the config — hard rule, AGENTS.md
section 7).

Primary scope (first submission): A1, A3, A4, A6, plus the adaptive attack A8.
A robustness claim without A8 is not a claim (AGENTS.md section 2): every
defense must be re-evaluated against A8 and checked for gradient masking and
budget leakage before reporting success.

Safety (hard rules, AGENTS.md section 2):

- generated adversarial files are written ONLY to
  ``datasets/processed/adversarial/`` and deleted after evaluation;
- never commit adversarial binaries — run records keep SHA-256 hashes;
- adversarial PEs are never executed anywhere: evaluation is parse + predict
  only, and any behavioral check is opt-in inside ``sandbox/``.

Invariants (tested in ``tests/unit/test_attacks.py``, P3):

- every edit keeps the file parseable (``pefile`` parse of the output);
- bytes outside the declared edit region are byte-identical to the original;
- the edit size respects the configured budget (Q, epsilon * N);
- attacks are deterministic given a seed from the config.

Implemented in P3. Until then the editors raise ``NotImplementedError``.
"""

from __future__ import annotations

__all__ = ["append_bytes", "inject_section", "pad_slack"]


def append_bytes(data: bytes, payload: bytes, budget: int) -> bytes:
    """A1-style append attack. Raises ``NotImplementedError`` until P3."""
    raise NotImplementedError("append_bytes lands with P3 (attacks + defenses)")


def inject_section(data: bytes, payload: bytes, budget: int) -> bytes:
    """A3-style section-injection attack. Raises ``NotImplementedError`` until P3."""
    raise NotImplementedError("inject_section lands with P3 (attacks + defenses)")


def pad_slack(data: bytes, budget: int) -> bytes:
    """A4-style padding-into-slack attack. Raises ``NotImplementedError`` until P3."""
    raise NotImplementedError("pad_slack lands with P3 (attacks + defenses)")
