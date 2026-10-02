"""Model zoo: baseline CNN, ResNet-50, MalConv, and the LightGBM feature head.

Primary scope (first submission): LightGBM, MalConv, baseline CNN, ResNet-50
on BODMAS. Anything else is out of scope without an ADR (AGENTS.md section 1).

Invariants (tested in P1):

- every model consumes the ADR-002 render/feature path — no bespoke resizing;
- every training run goes through ``runner/`` and writes a ``logger/`` record;
- seeds come from the config, never from code (hard rule, AGENTS.md section 2);
- weight files land in ``models/`` under versioned names and are registered in
  ``models/MANIFEST.md`` with the run ID and hash.

Implemented in P1. Constructors raise ``NotImplementedError`` until then.
"""

from __future__ import annotations

__all__ = ["BaselineCNN", "MalConv", "ResNet50Classifier", "LightGBMHead"]


class BaselineCNN:
    """Small CNN over the ADR-002 render. P1."""


class ResNet50Classifier:
    """ImageNet-pretrained ResNet-50 head over the ADR-002 render. P1."""


class MalConv:
    """Byte-level MalConv (no render; raw bytes + embedding). P1."""


class LightGBMHead:
    """LightGBM over static PE features (``pefile``-derived). P1."""
