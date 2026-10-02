"""Binary -> image rendering with a shared differentiable resize (ADR-002).

Scope: render a PE byte sequence into the image representation consumed by the
CNN/ResNet models, using the *identical* resize op at training, inference, and
attack time. One implementation, one import path; attack code must import the
resize from here, never redefine it.

Invariants (tested in ``tests/unit/test_render.py``, P0-P1):

- width-bucket policy is deterministic: same input size + config -> same bucket;
- padding value and policy are config-driven, not inline constants;
- the resize op is differentiable end-to-end (gradients flow for A8);
- attack pipeline and training pipeline resolve to the same resize callable.

Implemented in P1. Until then ``render_bytes`` raises ``NotImplementedError``.
"""

from __future__ import annotations

__all__ = ["render_bytes", "resize"]

ResizeConfig = None  # replaced in P1 by the typed config


def render_bytes(data: bytes, config: "ResizeConfig") -> "object":
    """Render a raw byte sequence to the model input image.

    Args:
        data: PE file bytes (read-only; callers must not mutate the source).
        config: width-bucket policy, padding value, output size.

    Raises:
        NotImplementedError: rendering lands in P1.
    """
    raise NotImplementedError("render_bytes lands with P1 (data + baselines)")


def resize(x: "object", size: tuple[int, int]) -> "object":
    """The shared differentiable resize op (ADR-002).

    Single source of truth for training, inference, and attacks.
    Raises ``NotImplementedError`` until P1.
    """
    raise NotImplementedError("shared resize lands with P1 (ADR-002)")
