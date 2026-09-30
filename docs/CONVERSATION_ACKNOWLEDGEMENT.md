# Optional parallel acknowledgement

The ordinary OmegaLLM goal path still uses one native Omega input loop with
its own memory, multimodal context and existing host/Jev/kernel validation.
No loop budget, goal deadline or retry policy changed.

An optional normal language call runs alongside it inside the same restricted
OmegaLLM container. This is a stateless speech companion, not a third remembering
agent or an action planner. Enable it with `STICKERBOOK_ACKNOWLEDGEMENT=1` in the
ignored **OmegaLLM-only** Docker env file, then recreate only that container.
Omit the flag or set it to `0` for the original single-call behavior.

It requires the existing OpenRouter credential and explicitly uses the existing
`z-ai/glm-5.2` profile with reasoning disabled. This adds one OpenRouter call
per powered utterance, even when another provider is selected for the goal.
The sponsored ASI `minimax/minimax-m3` goal lane remains unchanged. Public Pages
never calls this route. No keys reach the browser or are baked into images.

## Bounds

- Reply-only JSON, at most 600 characters and a requested 45–60 words, aiming
  for roughly 15–20 seconds of speech. Browser voice and speaking rate affect
  duration. Final results still interrupt interim speech rather than wait for it.
- Child text only: no images, coordinates, world snapshot, recall, tools,
  semantic goals, teaching, receipts or memory/history writes.
- One independent non-queuing gate per process, separate from the native goal
  gate. No retries or automatic provider fallback.
- Three-second provider I/O timeout; 3.5-second browser deadline. The host
  adapter uses a 3.5-second I/O timeout and 4 KiB reply limit.
- The browser starts the goal request first and never awaits acknowledgement
  before processing the result. Failed or late replies are discarded.
- Final response, page exit and voice disable cancel interim speech. Page exit
  during image capture also prevents sending the old request.
- Host and provider independently refuse extra fields, including goals.
  Tentative language is instructed by prompt, not guaranteed factual correctness;
  no statement from this companion grants action authority.

The flag is advertised through health/state capabilities. Older containers and
disabled configurations retain the existing path. Runtime failure is optional:
it cannot cause the normal goal to be retried, canceled or submitted twice.

## Qualification, September 30, 2026

Controlled ASI acknowledgement probes timed out at eight seconds, sequentially
and in parallel. Goal inference took 6.933 and 6.631 seconds respectively.
OpenRouter GLM-5.2 acknowledgement took 4.348 seconds normally versus 0.660
seconds with reasoning disabled. These small samples are not latency guarantees.

The actual parallel host path on isolated port 8763 produced:

| Request | Acknowledgement | Final response | Outcome |
| --- | ---: | ---: | --- |
| Tiny butterfly story | 0.715 s, 18 words | 11.273 s | Reply only; no world change |
| Butterfly, fly around the tree | 0.699 s, 18 words | 6.615 s | Powered play; nine accepted moves |

Both acknowledgement arrivals left the kernel revision unchanged at 2. The
directed request subsequently advanced to revision 15 through ordinary receipts.
A later no-acknowledgement control succeeded in 17.735 seconds. Provider
variability and memory/cache differences prevent claims about average latency
or performance regressions. These API samples have no image and do not qualify
visual target accuracy. Browser audio was not manually observed; word counts
do not measure speech duration or child patience.

Executable JavaScript tests cover early/final speech, late discard, failure,
timeouts, page races and request counts. RPC tests prove the separate gate works
while the native gate is held, refuses concurrent acknowledgements and shares
canonical process state. Host/provider tests refuse goals and oversized replies
without world changes. **520 web + 81 core + 40 Jev = 641 tests pass.**

The existing host on port 8760 and its play state were preserved. OmegaJev was
not restarted. OmegaLLM memory volumes and Docker restrictions are unchanged.
The opt-in test app is at `http://localhost:8763/?dev=1`.

### Longer speech follow-up

The later 45–60-word prompt produced 41 and 51 words in 1.693 and 1.111 seconds.
The updated host accepted a 55-word, 285-character reply in 0.965 seconds without
changing world revision. At 180 words/minute those are approximately 14, 17 and
18 seconds of speech; actual browser audio duration was not observed.
Provider timeout, parallel execution and cancellation are unchanged. The larger
host/browser envelope is 600 characters; completion budget is 300 tokens.
The updated preview is `http://localhost:8764/?dev=1`; earlier sessions were kept.
