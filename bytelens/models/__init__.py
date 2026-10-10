"""Model zoo: baseline CNN, ResNet-50, MalConv, and the LightGBM feature head.

Primary scope (first submission): LightGBM, MalConv, baseline CNN, ResNet-50
on BODMAS. Anything else is out of scope without an ADR (AGENTS.md section 1).

Implemented: LightGBM feature baseline (ADR-010 §5). Still P1 stubs: the
render-consuming models (BaselineCNN, ResNet50Classifier, MalConv) — they
need the ADR-002 render pipeline.

Invariants (tested in P1):
- every model consumes the ADR-002 render/feature path — no bespoke resizing;
- every training run goes through runner/ and writes a logger/ record;
- seeds come from the config, never from code (hard rule, AGENTS.md section 2);
- weight files land in models/ under versioned names and are registered in
  models/MANIFEST.md with the run ID and hash.
"""

from __future__ import annotations

from bytelens.models.lightgbm_baseline import MODEL_NAME, predict, resolve_params, train_lightgbm

__all__ = ["MODEL_NAME", "predict", "resolve_params", "train_lightgbm"]


class BaselineCNN:
    """Small CNN over the ADR-002 render. P1."""


class ResNet50Classifier:
    """ImageNet-pretrained ResNet-50 head over the ADR-002 render. P1."""


class MalConv:
    """Byte-level MalConv (no render; raw bytes + embedding). P1."""
