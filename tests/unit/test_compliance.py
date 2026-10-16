"""Compliance/fix-it PR template unit tests.

These tests exist so the template does not drift out of sync with the repo's
current governance files and the no-co-author rule.
"""
from __future__ import annotations

import os
import subprocess
import textwrap
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

PR_TEMPLATE = ROOT / ".github" / "PULL_REQUEST_TEMPLATE" / "compliance-fix-it.md"


def read_pr_template() -> str:
    assert PR_TEMPLATE.exists(), f"PR template missing at {PR_TEMPLATE}"
    return PR_TEMPLATE.read_text(encoding="utf-8")


def test_pr_template_exists_and_nonempty() -> None:
    text = read_pr_template()
    assert text.strip(), "PR template must not be empty"


def test_pr_template_links_governance_artifacts() -> None:
    text = read_pr_template()
    for anchor in ("AGENTS.md", "ADR-006", "ADR-011", "contracts/", "CHANGELOG.md"):
        assert anchor in text, f"PR template should reference {anchor}"


def test_pr_template_contains_no_coauthor_rule() -> None:
    text = read_pr_template()
    lowered = text.lower()
    assert "co-authored-by" in lowered or "co author" in lowered, (
        "PR template should explicitly mention the no co-author rule"
    )


def test_repo_latest_commit_has_no_coauthor_trailer() -> None:
    completed = subprocess.run(
        ["git", "log", "-1", "--format=%B"],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=True,
    )
    body = completed.stdout
    for line in body.splitlines():
        if line.strip().lower().startswith("co-authored-by"):
            raise AssertionError(
                "Latest commit carries a Co-Authored-By trailer; the repo rule is "
                "no co-author trailers."
            )
