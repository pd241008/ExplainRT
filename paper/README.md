# Paper

LaTeX source and figures for the TIFS submission
(`malware_tifs_paper.tex` — not yet present; it is the spec for names, G1–G3,
A1–A8, S1–S7, and metrics. Per AGENTS.md §1, stop and ask a human for it
before P2 work depends on it).

Rules (hard rule, AGENTS.md §2 + §8):

- **No number enters the paper unless it traces to a run ID, config, and seed
  in `logger/`.** Tables and figures are generated from run records by scripts
  here — never typed by hand.
- Figures: generated from `logger/` data by scripts in this directory.
  Do not commit generated figures; commit the scripts that produce them
  (Design Dungeons: no generated artifacts in git, prevent result drift).
