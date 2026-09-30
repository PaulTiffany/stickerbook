# Mapping design history

## Pre-freeze check 0.1

The first deterministic sonification encoded page identity, action class, receipt status,
stale-response timing, cross-page state deltas, and a revision/boundary cue.

A byte-level aligned/violation separation check found one collision:

- `action_set_validity`: **visual separated / sonic collided**.

Reason: the sonic mapping encoded the selected action class and accepted receipt, but not
whether a host-table selection was actually present in the host-offered legal-key set.
The aligned and injected-violation traces therefore produced identical WAVs.

Before any human data collection, the sonic mapping was revised to add a brief redundant
legal-membership alert for a host-table selection absent from the offered set. The source
fixtures were unchanged. The post-revision check reports all seven aligned/violation
pairs byte-distinct in both renderers.

This is a renderer calibration result only. Byte-level difference does not establish
human perceptual discriminability or diagnostic value.


## 2026-09-30 — observed runtime evidence layer

Imported four conservative observations from StickerBook `video/data/proof.json` (capture 2026-09-30T08:33:50Z; pinned blob SHA `2adf39be05d9b84b57341e1f3f58f64eb37c17c4`). The layer is intentionally positive-only and separate from synthetic matched perturbations. Claims are limited to what the artifact actually serializes: direct Jev provenance/accepted receipts, child interruption and move, page-state persistence, and language-to-bounded-goal translation. The artifact does not serialize the complete offered legal table for double-tap, does not inject a delayed live provider response across pages, and does not verify the hardened OpenShell live graph.
