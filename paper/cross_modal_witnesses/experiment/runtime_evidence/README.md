# Observed StickerBook runtime evidence

These traces are **observational runtime excerpts**, not synthetic calibration fixtures and not matched violation pairs.
They are conservatively derived from StickerBook's committed `video/data/proof.json`, captured at **2026-09-30T08:33:50Z** and available at the pinned repository commit recorded in `source.json`.

The source artifact labels itself `actual-live-runtime-evidence` and records isolated host `BookBridge` worlds calling the existing loopback Omega containers and producing ordinary kernel receipts. The video reconstructs those receipts rather than presenting a screen recording.

## Included observations

- `direct-control.observed.json` — direct double-tap reached Jev-controlled behavior with `translatedBy: null`; ordinary kernel receipts were accepted. The legal action table itself was not serialized in the proof artifact, so this observation does **not** independently test offered-key membership.
- `human-authority.observed.json` — active motion stopped with audit reason `child-grabbed`; an ordinary child move then received an accepted kernel receipt.
- `page-state-isolation.observed.json` — Farm state at revision 38, empty Space at revision 0, then identical restored Farm state. This is state-isolation evidence, **not** a live stale-response injection test.
- `language-goal.observed.json` — “Make the butterfly flutter.” produced a bounded goal (`subject=butterfly-1`, `intent=animate`, `behavior=flutter`) and Jev result `playing` in 5.49 s. The committed excerpt does not itself contain the subsequent kernel receipt for this language turn, so no stronger claim is made.

These observations supplement the synthetic calibration pairs. They do not replace the planned controlled perturbation study.
