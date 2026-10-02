"""Defenses: input canonicalization (D1), adversarial training (D2), ECT, ECT-A.

ECT (Explanation-Consistency Training) penalizes inconsistency between the
model's prediction and its explanation under PE-valid attacks. ECT-A is the
adaptive-attack-aware variant. The collapse guard (ADR-005) wraps every ECT
run with tolerances pre-registered on an earlier validation window.

Hard rules (AGENTS.md section 2):

- Never tune on test windows. Thresholds, beta, gamma, and the collapse-guard
  tolerance are chosen on an earlier validation window and written in an ADR
  BEFORE the runs that use them.
- Same tuning budget for every method (Arp et al. pitfall P5): no extra tuning
  for ECT. The budget per method is recorded in configs and compared.
- Report negative results: if ECT collapses or loses to canonicalization, the
  postmortem registry gets an entry — no silent swaps.

Invariants (tested in P3): defenses compose with the shared ADR-002 resize and
the A1/A3/A4/A6/A8 attack suite without special-casing.

Implemented in P3. Until then the entry points raise ``NotImplementedError``.
"""

from __future__ import annotations

__all__ = ["canonicalize", "adversarial_training", "ect_loss"]


def canonicalize(data: bytes) -> bytes:
    """D1: input canonicalization before feature extraction.

    Raises ``NotImplementedError`` until P3.
    """
    raise NotImplementedError("canonicalize lands with P3 (attacks + defenses)")


def adversarial_training(model: object, config: object) -> object:
    """D2: adversarial training loop (runner-driven). Raises until P3."""
    raise NotImplementedError("adversarial_training lands with P3")


def ect_loss(model: object, batch: object, beta: float, gamma: float) -> object:
    """Explanation-consistency loss with beta/gamma from the config only.

    beta and gamma must come from a pre-registered ADR/window, never tuned on
    test data. Raises ``NotImplementedError`` until P3.
    """
    raise NotImplementedError("ect_loss lands with P3")
