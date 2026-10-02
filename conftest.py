"""Pytest bootstrap.

The repo uses root-level packages (``bytelens``, ``logger``, ``runner``) per
the AGENTS.md section 4 layout. A conftest.py at the repo root makes pytest
prepend the root to ``sys.path`` (default import mode), so tests can import
them without installing the project.
"""
