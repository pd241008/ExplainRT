# Notebooks

Numbered, chronological EDA and pilot notebooks only
(`01_bodmas_eda.ipynb`, `02_shortcut_pilot.ipynb`, …).

Rules:

- Notebooks are **never the source of paper numbers** (AGENTS.md §1, §8).
  Anything that becomes a result moves into `bytelens/` + `configs/` + `runner/`
  and re-runs through the runner into `logger/`.
- No notebook ever loads or executes a sample from `datasets/raw/` — parsing
  raw files happens on the host only via `pefile`, read-only; anything else
  belongs in `sandbox/`.
- Notebooks are committed without output cells (`jupyter nbconvert --clear-output`).
