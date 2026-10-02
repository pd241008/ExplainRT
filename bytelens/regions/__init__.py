"""Canonical, flag-based PE region partition (ADR-001).

Partitions every byte of a PE into exactly one region label. Classification is
flag-based (PE section characteristics such as executable/writable flags and
RVA ranges), **never name-based**: section names are attacker-controlled and
untrusted (an attacker can rename ``.text`` to ``.data``).

Invariants (tested in ``tests/unit/test_regions.py``, P0-P1):

- every input byte receives exactly one label (total and disjoint partition);
- flag-based classification survives renamed sections (a renamed .text is
  still classified executable);
- headers, section table, and slack regions get their own labels so attacks
  can never silently touch them;
- the label set is versioned: a partition produced by one version is
  distinguishable from another in run records.

Implemented in P1. Until then ``partition_bytes`` raises ``NotImplementedError``.
"""

from __future__ import annotations

__all__ = ["partition_bytes", "RegionLabel"]


class RegionLabel:
    """Versioned enumeration of region labels (headers, code, data, slack, ...).

    Populated in P1 alongside the partition implementation.
    """


def partition_bytes(data: bytes) -> list[RegionLabel]:
    """Return exactly one label per input byte.

    Raises ``NotImplementedError`` until P1.
    """
    raise NotImplementedError("flag-based partition lands with P1 (ADR-001)")
