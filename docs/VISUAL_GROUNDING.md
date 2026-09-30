# Visual meaning, narrative, and governed movement

OmegaLLM interprets the child's language **and** observes page pixels. OmegaJev
does not receive images. It receives the admitted goal, target, current motor
context, taught pattern descriptions, and finite host-owned choices. Neither
container receives a kernel, filesystem mount, or spatial writing authority.

The powered browser captures its current page SVG when a child speaks or types.
It clones artwork and stickers, replaces presentation tween positions with the
accepted state endpoints, and excludes reference and placement overlays. It
inlines same-origin image resources and rasterizes a JPEG with maximum dimension
1024 and maximum data-URL length 180,000 characters. Capture creates no receipt.
The image carries page, revision, and dimensions. Page changes during capture
cancel the turn. Resource fetching is bounded by a five-second timeout; capture
failure leaves an ordinary structured/text turn rather than a fabricated image.

The host validates page identity, non-future revision, dimensions, JPEG header
dimensions, base64, and size. Conversation HTTP input permits at most 240 KiB;
other ordinary routes keep their existing 8 KiB bound. The Omega RPC bound
remains 256 KiB. Images are observation from the browser, not authoritative
world facts. They are not persisted as learned patterns or added to history.
Sticker identity and current state remain kernel facts. Pixels may be older
than current positions while an activity is moving. Legacy procedural Farm
feature coordinates are omitted from the visual conversation view because
they do not accurately describe the current raster artwork.

The provider sends an actual image content block, separately from scene JSON,
using the selected existing inference lane. OpenAI-compatible and Anthropic
formats are covered. Text-only requests retain their old wire format. Image
text is untrusted scenery, never an instruction or a command. Ambiguous visual
references should elicit clarification.

There is no new public goal schema. An artwork reference becomes an ordinary
normalized point; a placed sticker reference becomes an exact sticker id.
The existing short behavior field carries relations such as circling, perching,
or sitting. The host admits that goal and Jev selects steering. Every body tick
still goes through an ordinary kernel proposal and receipt. A targeted landing
request now enters travel rather than taking the old "land here" shortcut;
untargeted settling and explicit stop still cancel travel.

Narrative is reply-only unless the child clearly requests an action. Imaginative
story events are not receipts. This observation seam can inspect arbitrary
rendered artwork and future child-supplied pages/stickers without hardcoded
sun/barn/chair coordinates. Registering complete uploaded governed books and
sticker definitions is **not** implemented by this change.

## Qualified inference lanes

- ASI Cloud `minimax/minimax-m3`: image input qualified on the existing sponsored,
  locked profile. No new credential or model selection was introduced.
- OpenRouter `z-ai/glm-5.2`: text succeeds; an image request returned HTTP 404
  indicating unsupported image input. The provider preserves this exact profile
  as a text fallback, explicitly marking the missing visual observation in its
  input. It must not pretend it inspected the picture. The host response exposes
  `observation.imageUsed` truthfully. Other adult-selected profiles retain their
  selected transport; unsupported image requests fail closed.
- Public GitHub Pages: no capture-to-provider path and no model access.

Only OmegaLLM was rebuilt/recreated. OmegaJev was untouched. Non-root 65534,
cap-drop ALL, no-new-privileges, read-only root, bounded tmpfs/resources, separate
networks, loopback-only ports, and no host bind mounts remain in place. Ordinary
Docker is local development containment, not OpenShell-equivalent mediation.

## Live evidence and limitations

Real host/provider qualification used the Farm artwork rasterized with its
placed Cow and Butterfly; it did not use touch or box cues. A story took 17.620
seconds, returned narrative, and preserved kernel revision 2. "Butterfly, fly
around the sun and keep flapping" took 24.953 seconds and returned a bounded
target (.87,.13) with circle behavior. Jev chose AROUND-LEFT + flutter followed
by five AROUND-LEFT choices, with 29 receipts in an eight-second observation.
These are kernel-observed choices and geometry, not a claim of human visual QA.

A counterfactual, inference-only check mirrored the supplied artwork while
keeping the scene facts and utterance unchanged. The returned sun point moved
from (.88,.12) to (.15,.22), demonstrating sensitivity to image content rather
than a Farm landmark lookup. Points remain approximate: the actual unmirrored
sun center is about (.82,.19), and barn-roof outputs varied. Bounds validation
does not establish perceptual correctness. Precise perching and seating need
further product qualification; a valid point is not proof of successful sitting.

Inference-only checks also returned `cow-1` for "fly near the cow". A previously
unseen fixture containing three drawn chairs and no chair coordinates/catalog
returned the blue middle chair seat at (.5,.6), in 6.628 seconds. This qualifies
the visual interpretation seam, not uploaded-world registration or an executed
chair action. A fallback image-bearing request succeeded as a disclosed
text-only response with `image_used=false` after preserving the GLM text lane.

The motor scene now exposes at most six recent steering headings as typed,
bounded advisory evidence, alongside existing taught patterns. It contains no
historical executable keys. The contract permits varied exploratory play and
relational steering without forcing it. An eight-second free-play double-tap
still chose flutter + CONTINUE followed by repeated CONTINUE, even with recent
headings visible. **Spontaneous varied play remains unresolved.** No random
host override or forced action sampling was added to make a demonstration pass.

Continuous child-taught movement style, reinforcement/reward learning, reliable
arrival/settling, and perceptual confidence are not claimed solved. Existing
discrete memories remain advisory. ASI language/vision interpretation latency
also remains noticeable; immediate child grabbing still overrides autonomous
movement and late inference cannot restart a revoked invitation.

## Next learning seam

The child's goal is cumulative shaping, not a host-authored dance. Omega is the
intended owner of agent memory and continuity; Jev is its decision inference.
The current Jev RPC adapter reads probabilities into its trace but returns only
the winning key. It forwards no reward and updates no learned preference policy.
Advising "vary" is not reinforcement learning.
TypeSafe describes the base model's training as RLCD; that does not demonstrate
online updating of this application's hosted inference calls. OpenRouter's
[Decisions guide](https://openrouter.ai/blog/tutorials/how-to-use-jev/) documents
typed probability distributions suitable for an explicit application policy.

Inspection of the pinned running Omega source confirms that `getContext` includes
`getHistory`, and native memory supplies remember/query/episode operations. Our
RPC provider constructs its inference view solely from the host request instead
of that context. The channel delivers only a `STICKERBOOK-RPC` request-id marker;
the fixed return skill produces `SB-RPC-RETURNED`. Child teaching and accepted
world receipts therefore do not automatically become useful Omega experiences.
The hardened command allowlist also excludes unrestricted recall/remember skills.
Restoring the whole raw prompt or arbitrary skills is not the right repair.

The next integration should feed bounded accepted motion episodes and explicit
child feedback into Omega-owned memory, then expose narrowly projected relevant
recall as advisory state for Jev. This is not a replacement host-side learner.
Current taught pattern descriptions and recent steering are useful but do not
constitute that full Omega memory loop. The current Docker memory/chroma locations
are tmpfs, so persistence across recreation also needs deliberate qualification.

A subsequent reward loop can preserve and strictly validate the distribution
against the CURRENT legal table, support bounded exploration instead of always
choosing its winner, and bind positive/negative child feedback to a specific
accepted motion episode. OmegaLLM can interpret spoken teaching such as "I like
that twirl"; the host must resolve which actual episode the child means. Omega's
retained feedback/examples should then inform later Jev evaluations and the
OmegaJev agent's learned preferences. Memory and policy may change; legal actions must still
come solely from the current host table, with child interruption taking priority.

This is a direction for genuine adaptation of the OmegaJev agent, not a claim
that simply passing praise modifies the remote model weights. Persisting,
updating, credit assignment, probability validation, exploration policy, and
before/after learning evidence need their own focused implementation and tests.
No reward subsystem or probability sampling was silently introduced here.

## Verification

Tests cover both multimodal wire formats, ordinary text compatibility, explicit
text fallback, narration without mutation, page/revision/dimension/size bounds,
pixel-free Jev semantic handoff, the actual browser snapshot function with
accepted endpoint transforms and inlined artwork, public-mode exclusion,
target-bearing landing, and bounded recent steering evidence. The complete
suite comprises 490 web tests, 81 core authority tests, and 40 Jev tests (611).
JavaScript syntax and the existing runtime integration verification also pass.
Browser snapshot rendering is covered by a deterministic DOM/canvas harness;
live inference evidence used rasterized actual artwork. A full interactive
browser capture was not manually inspected in this qualification.
