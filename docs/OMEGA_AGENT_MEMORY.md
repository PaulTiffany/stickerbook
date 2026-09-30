# Two Omega agents, two memories

<img src="../assets/_generated_sprite_refresh/cropped/robot/wave.png" alt="Robot StickerBook sticker" width="125">

OmegaLLM and OmegaJev now each use Omega's native Chroma `remember`,
`query_with_ids`, and strength/confidence (STV) functions. The existing pinned
Omega local embedding implementation supplies vectors. These are separate
agent stores, not a shared host learner or a transcript passed through as skills.

OmegaLLM remembers validated child conversations and replies. Its provider
retrieves at most three bounded conversation notes for continuity, preferences,
and storytelling. Current host state always takes precedence over recall.

OmegaJev remembers accepted movement and clip experience, including child
demonstrations. Host evidence groups contain at most six accepted moves, their
start/end, heading-change count, and up to four clips. Refused/replayed receipts
do not become new experience. Child and Jev sources remain distinct. The host
courier queues at most 32 groups and keeps 12 recent groups for linguistic
reference; it owns neither durable memory nor a learning policy.

For explicit praise or correction, OmegaLLM can propose a bounded `teaching`
description referencing an experience actually offered in the current scene.
The host validates that reference and page, then sends the accepted experience
and feedback to OmegaJev's memory endpoint. Positive/negative feedback adjusts
the native experience strength by +0.1/-0.1, clamped to [0,1], and confidence
by +0.05, capped at 0.99. New experience starts at strength/confidence 0.5/0.5.
Unknown references cannot create rewards. Ambiguous feedback should ask which
experience the child meant. Storage failure produces an honest bounded reply.

Jev's provider retrieves at most three same-page, same-asset advisory notes.
Explicit teaching is prioritized, with semantic ranking within each category.
Recalled notes contain no old action keys, subject IDs, or coordinates. They
remain inside the existing 4,000-character decision view; optional context is
trimmed when necessary. Known patterns remain advisory context when they fit.
The only executable Omega command remains the zero-argument `sb-return`.

## Authority and interruption

The browser still talks only to the host. The two agents do not communicate
directly. OmegaLLM mediates language, including proposed feedback; OmegaJev
selects an offered key; the host resolves it into bounded primitives; the kernel
independently accepts/refuses each mutation. Memories grant no actions and cannot
override current legal choices, child intervention, or page cancellation.

Native document embedding and delivery run outside the host world lock.
Background document encoding also runs outside the native-store lock, so it
does not block recall while encoding new evidence. Repeated query embeddings
use a 32-entry process cache; embedding threads are limited to the container's
two-CPU budget. Store/query/index operations themselves remain serialized.

## Persistence and scope

Each local Docker agent has its own two named volumes: `stickerbook-jev-local`
or `stickerbook-llm-local` followed by `-chroma` and `-memory`, mounted at
`/PeTTa/chroma_db` and `/PeTTa/repos/Omega/memory`. These persist container
recreation. There are no host bind mounts, repository mounts, or Docker socket.
Volumes are writable by UID/GID 65534. Separate networks, localhost ports,
read-only root, cap-drop ALL, no-new-privileges and resource limits remain.
This remains LOCAL POWERED DEV with direct provider credentials/egress, not
OpenShell-equivalent containment.

The typed index keeps at most 256 records per agent and evicts corresponding
native documents. Native Omega's own loop/history files also live in its memory
volume; this limit is not a physical disk quota. Native store and index writes
are not one crash-atomic transaction. Delivery is bounded and best effort, with
no unlimited retry. Logical event IDs deduplicate normal repeated delivery.

Recall is page-scoped and Jev recall is additionally asset-scoped. A butterfly's
feedback can inform a newly placed butterfly on that page, deliberately without
making an old subject ID a current fact. Existing host pattern memory retains
its separate established scope. This local installation has no child accounts:
its durable memory belongs to the local agent, not an authenticated individual.
Do not present this as multi-user isolation.

`GET /memory` exposes fixed role/backend/count/cap metadata; `/memory/events`
accepts only the role's bounded typed records. Neither endpoint executes commands
or returns a raw transcript. Canonical RPC process state owns the memory object,
so Omega's plugin execution and the provider's normal import share it even when
the channel source executes twice.

## Live qualification

With ASI Cloud `minimax/minimax-m3`, OmegaLLM remembered the child's fixture
nickname River and preference for silly butterfly stories on a later turn.
Its two initial records survived container recreation.
After a subsequent recreation, it again recalled both preferences in 4.692
seconds. OmegaJev's persisted lesson retained strength 0.4/confidence 0.55;
its resumed play recalled three notes and selected small turns in roughly
0.99–1.11 seconds. Native recall on Beach returned no Farm notes for either
agent. Grabbing the butterfly stopped resumed play in 3 ms.

With OpenRouter `typesafe/jev-1.13`, the baseline butterfly chose mostly
CONTINUE. A spoken correction requested gentle curves instead of straight
flight. OmegaLLM returned a valid teaching reference; the host stored one
negative lesson. The next eight-second play episode selected LEFT-SMALL six
times, with recalled context on each decision. Latencies were 0.418, 1.020,
1.024, 0.974, 1.611, and 1.073 seconds. Human grabs returned in 2–6 ms and stopped
play. Subsequent play continued to recall the lesson and also selected small
right turns. This is observable feedback-conditioned behavior, not proof of
durable generalization from a controlled study.

An initial malformed two-object teaching response was refused; the prompt was
corrected to request one JSON object. A subsequent ASI request timed out at the
existing 40-second host deadline. The successful correction took 19.775 seconds;
linguistic feedback latency remains a product limitation. No timeout was treated
as accepted teaching or world authority.

## What is not solved

This changes memory and inference context, not Jev's underlying model weights.
It does not introduce online training, probability sampling, a host-authored
choreography, or guaranteed behavioral diversity. Repeating small left turns
can itself become monotonous. The child can shape later selections, but broader
exploration and learning evaluation remain research work.

Bounded geometric evidence and existing discrete patterns are not yet full
continuous movement-style learning. Future named motifs can build on these
accepted experiences without turning historical coordinates into executable
authority. Public GitHub Pages remains deterministic/mechanical with no model
or native agent-memory access.
