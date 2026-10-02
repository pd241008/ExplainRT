"""Explanations: Grad-CAM, Integrated Gradients, Score-CAM, faithfulness, collapse guard.

Serves RQ3 (explanation sanity/faithfulness) and provides the consistency
signal for the ECT defense (RQ4).

Invariants (tested in ``tests/unit/test_explain.py``, P2):

- CAM back-projection round-trips offsets for H != W (non-square inputs);
- per-region explanation masses sum to 1 within float tolerance;
- the randomization sanity check (Adebayo et al. style) materially degrades
  maps — if it does not, the explanation method is rejected as a paper metric;
- faithfulness metrics (deletion/insertion) are computed against the same
  ADR-002 resize path used by the attacked model.

Implemented in P2. Until then the public functions raise ``NotImplementedError``.
"""

from __future__ import annotations

__all__ = ["grad_cam", "integrated_gradients", "score_cam", "region_masses"]


def grad_cam(model: object, x: object, target: int | None = None) -> object:
    """Class-discriminative Grad-CAM map for the rendered input.

    Raises ``NotImplementedError`` until P2.
    """
    raise NotImplementedError("grad_cam lands with P2 (explanation audits)")


def integrated_gradients(model: object, x: object, steps: int = 50) -> object:
    """Integrated Gradients attribution. Raises ``NotImplementedError`` until P2."""
    raise NotImplementedError("integrated_gradients lands with P2")


def score_cam(model: object, x: object) -> object:
    """Score-CAM attribution (supplement). Raises ``NotImplementedError`` until P2."""
    raise NotImplementedError("score_cam lands with P2 (supplement)")


def region_masses(attribution: object, regions: object) -> object:
    """Aggregate a pixel-space attribution into per-region masses summing to 1.

    Raises ``NotImplementedError`` until P2.
    """
    raise NotImplementedError("region_masses lands with P2")
