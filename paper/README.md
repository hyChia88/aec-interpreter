# Research paper (LaTeX assembly)

Compilable research paper following the standard structure (Intro w/ related work +
contributions → System Design → Evaluation → Discussion → Conclusion), per the draft
structure in `AEC Interpreter - org.md`. The earlier RQ-chapter drafts live in
`docs/thesis/*.md` (markdown source) and `sections/archive_rq_chapters/` (their LaTeX
ports); their content is redistributed into the paper sections.

## Build

Toolchain on this host: `pdflatex` + `bibtex` (no `latexmk`/`tectonic`).

```
make            # pdflatex → bibtex → pdflatex ×2 → main.pdf
make clean      # remove aux files, keep PDF
make cleanall   # remove everything generated
```

## Layout

- `main.tex` — article-class preamble + `\input` of the sections.
- `sections/` — `00_abstract`, `01_introduction` (motivation, RQs, related work, contributions,
  scope), `02_system_design` (design rationale, architecture, IFC engine, VLM, synthetic data,
  symbolic layer, spatial address + routing), `03_evaluation` (oracle → neural → union →
  realized/calibrated → depth law → failure/latency/triage), `04_discussion` (workflow,
  limitations, future work), `05_conclusion`.
- `sections/archive_rq_chapters/` — the earlier RQ-chapter LaTeX drafts (superseded).
- `references.bib` — copied from `docs/thesis/references.bib` (keep in sync). 15 entries,
  all programmatically verified (arXiv API / doi.org BibTeX).
- `figures/` — copied from `output/` + user-staged (`system_decomposition.png`,
  `vlm_implementation.png`).

## Before camera-ready

- **`chiahuiyen_mscd_thesis`**: confirm the exact title and year of the prior MSCD thesis in
  `references.bib` (currently placeholder title + year 2025).
- Published-venue fields (ICML/NeurIPS/ICLR booktitles) were hand-added on top of the
  arXiv-verified anchors — double-check.
- **[CITATION NEEDED]** in `01_introduction.tex` (related work): the org note names
  "Li et al. 2024" and "Wang et al. 2024" (pixels-to-graphs VLMs) — could not be verified;
  confirm which papers these are before citing.
- Figures the org draft wants that don't exist yet: landscape positioning diagram
  (determinism × generality quadrant) and synthetic-data-pipeline diagram.
