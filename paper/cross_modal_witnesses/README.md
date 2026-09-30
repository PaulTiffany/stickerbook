# Cross-Modal Witnesses

LaTeX manuscript for:

**Cross-Modal Witnesses: Perceptual Transduction as an Audit Surface for Agentic Alignment**
Paul Carver Tiffany III
ORCID: [0009-0003-4785-6797](https://orcid.org/0009-0003-4785-6797)

## Public artifacts

- [I'm Upping My P(HOP) — YouTube](https://youtu.be/vpu4tmhyj04)
- [StickerBook — GitHub](https://github.com/PaulTiffany/stickerbook) · [public mechanical demo](https://paultiffany.github.io/stickerbook/)
- StickerBook implementation records: [authority kernel](https://github.com/PaulTiffany/stickerbook/blob/main/core/README.md) · [OmegaJev experiment](https://github.com/PaulTiffany/stickerbook/blob/main/jev/EXPERIMENT.md) · [agent interface](https://github.com/PaulTiffany/stickerbook/blob/main/docs/AGENT-INTERFACE.md)
- Pinned P(HOP) evidence: [runtime proof JSON](https://github.com/PaulTiffany/stickerbook/blob/453a90f846c61b9c5c8c8f007db4e85ce307fa28/video/data/proof.json) · [video reproducibility record](https://github.com/PaulTiffany/stickerbook/blob/453a90f846c61b9c5c8c8f007db4e85ce307fa28/video/README.md) · [governed runtime status](https://github.com/PaulTiffany/stickerbook/blob/453a90f846c61b9c5c8c8f007db4e85ce307fa28/runtime/README.md)
- [The Cost of Cacophony](https://github.com/PaulTiffany/cost)
- [The Hypothesis Surface — GitHub](https://github.com/PaulTiffany/hypothesis-surface-agi26) · [project page](https://paultiffany.github.io/hypothesis-surface-agi26/)
- [Principia Symbolica — GitHub](https://github.com/PaulTiffany/Principia-Symbolica) · [project page](https://paultiffany.github.io/Principia-Symbolica/) · [Book IV atlas records](https://paultiffany.github.io/Principia-Symbolica/atlas/book-iv-de-identitate-symbolica-et-emergentia/page-1/)

## Build

With `latexmk`:

```bash
latexmk -pdf main.tex
```

Or manually:

```bash
pdflatex main.tex
biber main
pdflatex main.tex
pdflatex main.tex
```

## Files

- `main.tex` — manuscript
- `references.bib` — BibTeX bibliography
- `main.pdf` — compiled submission manuscript
- `figures/cross_modal_pipeline.tex` — source trace -> modality transforms -> observers -> disagreement/triage
- `figures/collision_impossibility.tex` — anti-masking / representation-collision proposition
- `figures/shared_bottleneck.tex` — false multimodal reassurance under a shared lossy intermediate
- `figures/stickerbook_apparatus.tex` — bounded StickerBook decision and page-isolation apparatus
- `figures/phop_ingress_loop.tex` — recursive P(doom) -> observer -> P(HOP) -> re-ingress provenance loop
- `figures/calibration_pair.tex` — matched aligned/page-leak calibration witness schematic
- `figures/runtime_observed.tex` — observed StickerBook runtime evidence and explicit claim boundary
- `experiment/` — synthetic calibration fixtures, observed runtime evidence, witness renderers, manifests, checks, and runtime-export adapter

## Current status

This is the September 30, 2026 submission manuscript: theory, proposed methods, synthetic calibration, and bounded observed runtime evidence. It includes:

- two formal impossibility results (single-transform collision and shared-bottleneck collision);
- a canonical StickerBook trace schema grounded in the current public authority-kernel/OmegaJev architecture;
- separate source-perturbation and mapping-perturbation protocols;
- a concrete first-pass sonification map with accessibility controls;
- a preregistration-ready mixed-effects analysis plan and transform-lineage audit;
- exact Book IV Principia Symbolica atlas anchors for observer kernels, bounded observers, projective translation, and observer locality;
- seven reproducible vector figures, including matched calibration and observed-runtime claim-boundary figures;
- a bundled empirical scaffold with 14 synthetic calibration traces, independent SVG/WAV renderers, stimulus hashes, and a preserved pre-freeze mapping-collision record;
- four separately labeled observed StickerBook runtime traces derived from the pinned P(HOP) proof artifact, with independent SVG/WAV witnesses and their own hash manifest; and
- direct links to the public artifacts motivating and instantiating the framework.

Strong next additions depend on empirical execution rather than more theory-only prose:

1. wire `experiment/runtime_export_adapter.py` into StickerBook for direct canonical capture rather than post-hoc projection from `video/data/proof.json`;
2. capture matched runtime perturbations where safe and mechanically controllable, especially stale-response rejection and page-boundary tests;
3. conduct a small perceptual pretest to verify that the frozen visual/sonic distinctions are discriminable without answer leakage;
4. run a small pilot to estimate variance and simulation-based power for the confirmatory observer study;
5. preregister and run the confirmatory observer study; and
6. add the empirical modality-comparison / disagreement-localization figure once participant data exist.

## HyperSprints support

StickerBook was made with support from [BGI Commons](https://bgicommons.org/) as part of its **HyperSprints series**. [StickerBook team page](https://bgicommons.org/teams/62).
