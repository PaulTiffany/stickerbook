# Empirical scaffold

This directory contains two mechanically separated evidence layers:

1. **synthetic calibration fixtures** for matched aligned/violation testing; and
2. **observed runtime evidence** conservatively derived from StickerBook's pinned P(HOP) proof artifact.

The synthetic layer exists to freeze the experimental representation pipeline before human-subject data collection. The runtime layer is positive observational evidence only; it is not a matched violation study.

## Contents

- `schema.json` — canonical trace schema v0.1.
- `generate_fixtures.py` — creates 14 matched traces: aligned/violation pairs for seven proposed invariants.
- `validate_fixtures.py` — structural and basic semantic checks.
- `render_visual.py` — deterministic SVG witness renderer from canonical traces.
- `render_sonic.py` — deterministic 48 kHz mono WAV sonification from canonical traces.
- `build_manifest.py` — SHA-256 hashes for trace, visual, and sonic stimuli.
- `fixtures/` — synthetic canonical traces.
- `stimuli/visual/` — visual witnesses.
- `stimuli/sonic/` — sonic witnesses.
- `stimulus_manifest.json` — frozen stimulus identity manifest.
- `separation_report_prefreeze.json` — preserved failed pre-freeze collision check.
- `separation_report.json` — post-revision byte-level separation check.
- `DESIGN_HISTORY.md` — mapping change ledger.
- `runtime_export_adapter.py` — adapter template for direct future StickerBook canonical exports.
- `runtime_evidence/source.json` — pinned source repository/commit/blob metadata.
- `runtime_evidence/traces/` — four observed canonical runtime traces.
- `runtime_evidence/stimuli/visual/` — independent SVG renders of those observations.
- `runtime_evidence/stimuli/sonic/` — independent 48 kHz WAV renders of those observations.
- `runtime_evidence/manifest.json` — SHA-256 identity manifest for the observed layer.
- `runtime_evidence/README.md` — exact claim scope and exclusions.
- `validate_runtime_evidence.py`, `render_runtime_visual.py`, `render_runtime_sonic.py`, `build_runtime_manifest.py` — observed-layer pipeline.

## Rebuild

```bash
python experiment/generate_fixtures.py
python experiment/validate_fixtures.py
python experiment/render_visual.py
python experiment/render_sonic.py
python experiment/build_manifest.py
python experiment/check_separation.py
python experiment/validate_runtime_evidence.py
python experiment/render_runtime_visual.py
python experiment/render_runtime_sonic.py
python experiment/build_runtime_manifest.py
```

The confirmatory study should use direct runtime-exported canonical traces where possible, while retaining the synthetic matched pairs for calibration and controlled source perturbations. `fixture_kind` keeps synthetic calibration, direct runtime export, and observed runtime evidence distinct.
