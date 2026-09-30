# Project lineage and developer context

> Current deployment: restricted ordinary Docker has been live-qualified locally. OpenShell
> remains the unresolved hardened target; references below to its policies describe that
> design lineage, not achieved local containment. See [submission disclosure](SUBMISSION_REVIEW.md).

This document records the human and project lineage behind StickerBook for
researchers, reviewers, and future maintainers.

It is intentionally separate from
[TOOLS-AND-MODIFICATIONS.md](TOOLS-AND-MODIFICATIONS.md). That ledger answers
"what software is present and what changed?" This document answers a different
question:

> **What earlier work and community engagement shaped the design choices that
> appear in StickerBook?**

The short conceptual lineage is:

~~~text
Chalked
  visible human/agent authority + provenance + staged trust boundary
       |
       v
AlphaClaw
  boundary outside the reasoner + bounded host controller + receipts +
  independent lifecycle/stop + explicit claims/non-claims
       |
       v
BGI Commons / Omega community engagement
  hosted-agent observability, operator control, provider ownership,
  legal-exposure and "who can actually stop it?" questions
       |
       v
StickerBook
  child-facing shared world + OmegaLLM/OmegaJev separation +
  host authority kernel + OpenShell containment + adult-owned inference
~~~

This is a conceptual lineage, not a claim that the projects are the same
system or that every StickerBook mechanism existed in an earlier repository.

## 1. Status of the claims in this document

Three evidence classes are kept separate.

### Public repository evidence

The Chalked and AlphaClaw descriptions below are grounded in their public
repositories:

- Chalked: https://github.com/PaulTiffany/chalked
- AlphaClaw: https://github.com/PaulTiffany/AlphaClaw

Those repositories are the primary sources for their architecture, experiment
records, and stated claims.

### Public BGI Commons context

BGI Commons describes itself as a community for building, learning, and
collaborating toward beneficial AI/AGI, including team-based HyperSprints:

- https://bgicommons.org/

Its September 2026 Terms and Privacy pages identify the SingularityNET
Foundation as the operator of the BGI Commons platform:

- https://bgicommons.org/terms
- https://bgicommons.org/privacy

### Developer-reported engagement

Paul Tiffany's participation in BGI Commons calls and related Omega/community
discussions is project-history context reported by the developer. It should not
be silently upgraded into a stronger institutional claim.

In particular, this repository does not claim that:

- Tiffany was employed by BGI Commons or SingularityNET Foundation;
- StickerBook is a BGI Commons deliverable;
- BGI Commons, SingularityNET Foundation, ASI Alliance, or any inference
  provider endorses StickerBook;
- BGI Commons reviewed or approved StickerBook's security model;
- Chalked or AlphaClaw were official upstream components of StickerBook.

Where formal sponsorship, employment, endorsement, or acceptance matters, use
a separate primary source rather than inference from technical proximity.

---

## 2. Chalked: authority made visible on the shared surface

Repository: https://github.com/PaulTiffany/chalked

Chalked was an OmegaClaw integration demo for ASI:Create / Track 2. Its object
was deliberately simple: a shared whiteboard on which human and agent marks
could coexist while the authority relationship remained visible in the medium
itself.

The repository's core rule was:

- people write in a reserved trusted color, cyan;
- agents use non-cyan colors;
- people retain final say over human marks;
- agents may add marks and tidy agent marks;
- an agent is refused if it attempts to erase a human mark.

The important design move was not "use cyan." It was:

> **Put the authority contract on the surface where the user can perceive it.**

The color convention acted as visible provenance. A user did not have to
inspect an agent prompt or hidden policy file to understand that a human mark
and an agent mark occupied different authority classes.

### 2.1 Co-development provenance

Chalked's README also records an unusual authorship/process detail: the
deliverables were drafted and the agent layer was built through OmegaClaw on
MiniMax inference, with human-completed edits at the tool's break-points.

That matters to the lineage because Chalked was not only a demo about authority
between humans and agents; it was itself produced through a constrained
human-agent workflow. The sprint brief records concrete tool limitations,
permission edges, readback requirements, and points at which the agent was
expected to stop and return control to Paul.

This is an early form of the later StickerBook rule that a model can contribute
work inside a bounded surface without acquiring authority over the boundary
itself.

### 2.2 R0-R4: build the smallest real trust boundary first

CHALKED_ARCH_SPEC.md and SPRINT_BRIEF.md described a staged architecture:

- **R0 — ephemeral MVP:** one browser artifact; demonstrate the contract before
  claiming server enforcement;
- **R1 — persistence:** make the state durable and therefore identify who may
  write it;
- **R2 — server-side enforcement:** move the trust boundary into a small host
  process so a hostile or buggy client cannot rewrite the contract;
- **R3 — real provenance:** assign trusted provenance from the server/channel
  rather than trusting a client-selected color;
- **R4 — identity / real-time / policy surface:** add identity and stronger
  shared-system machinery only after the preceding boundaries are explicit.

That progression is important to StickerBook. Chalked explicitly distinguished
demonstrating a rule from enforcing a rule.

StickerBook keeps the same distinction:

- the public GitHub Pages build demonstrates the interaction medium
  mechanically;
- the powered local profile has an actual host authority kernel;
- art and browser behavior do not silently become authorization;
- new capability is introduced only with a named boundary and proof status.

### 2.3 Human-authored enforcement outside the agent

The Chalked sprint brief explicitly treated server-side security-critical
enforcement as a human-controlled break-point rather than something to leave
inside an agent-authored tool path.

That is a direct ancestor of StickerBook's current separation:

~~~text
agent/model output != world authorization
~~~

StickerBook generalizes the Chalked lesson from a whiteboard rule into typed
principals, ownership, action tables, revisions, budgets, and receipts in the
core authority kernel.

### 2.4 Readback and "success is not proof"

Chalked also records a practical lesson from working through constrained agent
tools: a tool reporting success was not treated as proof that the intended
bytes actually persisted. Work had to be read back.

That discipline survives in StickerBook as a broader provenance rule:

- model text is not proof of action;
- transport success is not proof of authorization;
- an inference reply is not proof that a sticker moved;
- authoritative state plus a receipt are the evidence of the governed result.

### 2.5 What StickerBook inherits — and what it does not

StickerBook inherits from Chalked:

- visible human/agent distinction;
- authority external to agent preference;
- explicit provenance;
- least-risk staged deployment;
- separation between demo and enforceable system;
- refusal as a first-class successful outcome;
- verification/readback rather than self-report.

StickerBook does not simply reuse Chalked's policy.

For example, StickerBook uses explicit principals and action-specific kernel
rules rather than treating color as sufficient identity. Chalked's cyan rule is
therefore best understood as a conceptual predecessor to StickerBook's typed
authority model, not as the current authorization mechanism.

---

## 3. AlphaClaw: put the boundary outside the reasoner

Repository: https://github.com/PaulTiffany/AlphaClaw

AlphaClaw's project line is:

> **Multimodal at the boundary. Text inference in the loop. Human authority
> around both.**

AlphaClaw is a sensory boundary and bounded experimental apparatus around a
pinned upstream OmegaClaw reasoning substrate. Its central architectural
experiment asks whether multimodal perception can happen once at ingress,
producing a fixed symbolic/text handoff for downstream text reasoning.

The significant StickerBook inheritance is not that StickerBook performs the
same perception experiment. It is the placement of the control boundary.

### 3.1 Separate perception, inference, accounting, and human development

AlphaClaw deliberately keeps several surfaces distinct:

1. multimodal perception at ingress;
2. pinned upstream OmegaClaw inference;
3. a host-owned benchmark controller;
4. isolated accounting/receipt machinery;
5. human development/documentation surfaces.

This is closely related to StickerBook's insistence that:

~~~text
language != decision selection != authorization != containment
~~~

StickerBook goes further by splitting its live Omega work into OmegaLLM and
OmegaJev, but the architectural habit is the same: do not let convenient
component boundaries collapse distinct causal roles.

### 3.2 Pinned upstream subject instead of a hidden fork

AlphaClaw's bounded experiments run stock, pinned OmegaClaw in fresh Docker
containers. The controller bounds and observes the experimental subject from
the host rather than silently rewriting the subject and then claiming to have
studied the original.

That is directly relevant to StickerBook's Omega discipline.

StickerBook does make explicit derived-image modifications and additions, but
it:

- pins the upstream Omega revision;
- documents every local modification;
- keeps those modifications additive and inspectable;
- distinguishes older experimental paths from the current browser-service
  path;
- avoids describing project-specific behavior as though it were stock Omega.

The shared research norm is:

> **Name the population you actually tested.**

### 3.3 Bounded controller and independent stop path

AlphaClaw's benchmark controller keeps the important experimental controls on
the host:

- finite reasoning-loop ceilings;
- finite provider-call budgets;
- fresh-container lifetime;
- provider metering;
- recording of raw usage receipts;
- stop and destruction outside the reasoning subject.

Its philosophy also makes explicit that a nominal stop control is insufficient
if the failing system can blind, delay, or disable the path used to observe and
stop it.

StickerBook inherits this directly:

- Start StickerBook.cmd and Stop StickerBook.cmd are operator-owned;
- the authority bridge is outside both Omega sandboxes;
- sandboxes can be deleted without model cooperation;
- OpenShell containment is outside the model's decision-making;
- the child does not acquire Docker, policy, or provider authority;
- adult inference choice is host state, not model state.

### 3.4 Receipts, frozen evidence, and claims/non-claims

AlphaClaw's v2/v3 research checkpoint is deliberately auditable from committed
artifacts. It separates provider receipts, run manifests, frozen stimuli, and
derived synthesis from narrative conclusions.

Under the tested bounded conditions, AlphaClaw reported:

- an operationally stable symbolic sensory boundary across the tested sensory
  substitutions;
- stronger outcome sensitivity to resident-model substitution than to the
  tested sensory substitutions;
- reproduction of a "correct token present but no valid emission" seam;
- a perceive-once cost structure in which multimodal calls remain constant at
  one while a multimodal-resident baseline scales with reasoning depth;
- measured savings in the reported deeper-turn OpenRouter experiment, while
  explicitly declining to generalize those results universally.

The important inheritance for StickerBook is methodological:

- preserve raw evidence;
- mechanically re-derive what can be re-derived;
- record limitations and non-claims next to claims;
- do not convert provider/model behavior into a timeless property of the
  architecture.

That is why StickerBook's documentation uses statuses such as IMPLEMENTED,
mechanically checked, VERIFIED for named claims, and NOT YET LIVE-HOST VERIFIED
rather than one global "works" label.

### 3.5 Capability is not permission

AlphaClaw's philosophy and experimental architecture repeatedly separate
capability from permission and recursive proposal from recursive
authorization.

StickerBook turns that principle into an operational world rule:

> **Capability is not authority.**

A better model, richer memory, more provider options, or a more capable Omega
loop does not automatically receive a larger legal action table.

The Responsible Adult inference selector is a current example: changing from
MiniMax to Claude, OpenAI, OpenRouter, or ASI:One changes the inference
substrate, not the authority graph.

---

## 4. BGI Commons: HyperSprints support and the hosted-agent control question

Public portal: https://bgicommons.org/

BGI Commons describes its purpose as bringing people together to build and
learn around beneficial AI/AGI, with resources, collaborators, groups, and
HyperSprints. Its published Terms and Privacy material identifies the
SingularityNET Foundation as platform operator.

StickerBook was made with support from BGI Commons as part of the HyperSprints
series; see [the project team](https://bgicommons.org/teams/62). It remains
independent research, with author-owned results and authority boundaries.

### 4.1 Developer-reported participation

During September 2026, Paul Tiffany participated in BGI Commons community calls
and discussions around Omega, hosted-agent systems, and possible HyperSprint
work.

One discussion concerned a hosted "free machine" / persistent-agent framing in
which the infrastructure owner and the user directing the agent could be
different parties. Tiffany's concern was that "inspectability" for the machine
owner is not automatically inspectability or control for the user who may be
treated as responsible for directing the system.

A recurring question was not merely "can the agent do this?" but:

> **If the platform controls the hosted machine while the user directs the
> agent, who actually has observability and control over the system whose
> actions may create legal or practical exposure?**

Related questions raised in those discussions included:

- whether a hosted "free machine" gives the directing user meaningful
  observability or mainly gives the infrastructure owner inspectability;
- who can inspect the live machine and at what layer;
- whether inspectability belongs to the infrastructure owner, the directing
  user, or both;
- who can stop or constrain the agent when the user and machine owner are
  different parties;
- how responsibility should be understood if an agent-directed action would
  be unlawful in a relevant jurisdiction;
- whether a user can reasonably bear responsibility for actions executed on a
  machine whose decisive telemetry or policy controls are held elsewhere.

These are project-history notes about the developer's questions and engagement,
not statements of BGI Commons policy or legal conclusions.

### 4.2 Why the local implementation mattered

The practical response was to explore a local, inspectable implementation
rather than treat a persistent hosted agent as the only meaningful deployment
target.

That pressure is visible in StickerBook's architecture:

- powered agent execution stays on the local development host;
- the public web demo is intentionally non-powered;
- the host bridge owns StickerBook world authority;
- OpenShell constrains each Omega role from outside the agent;
- the operator owns start and stop;
- provider credentials are mediated at an external boundary;
- inference provider/model choice belongs to the responsible adult;
- the system records where a decision came from rather than treating "the AI"
  as one undifferentiated actor.

This is the operational form of an earlier design question:

> **How do you box a hosted agent?**

StickerBook's present answer is deliberately narrower:

> For this research profile, do not begin by granting the hosted agent the
> whole box. Keep execution, containment, authority, and the stop path
> separately inspectable, and keep the powered profile local until the boundary
> is actually demonstrated.

### 4.3 Relationship to HyperSprint-style work

BGI Commons describes HyperSprints as short collaborative build efforts with
challenge tracks, teams, milestones, mentors, and submissions.

StickerBook is compatible with that build/research style — small inspectable
artifacts, explicit milestones, concrete demonstrations — but no claim is made
here that StickerBook is an accepted HyperSprint submission or official BGI
Commons challenge artifact unless a separate primary record establishes that.

---

## 5. Synthesis in StickerBook

StickerBook is not simply "Chalked with stickers" or "AlphaClaw with a child
UI." It combines lessons from both and applies them to a different research
object: a shared illustrated environment in which children and bounded agents
can manipulate persistent objects.

The synthesis can be read as:

| Prior pressure | StickerBook response |
|---|---|
| Chalked: make human/agent authority visible | child-facing medium plus explicit ownership/provenance and understandable refusal |
| Chalked: demo is not enforcement | public mechanical Pages profile vs powered authority-kernel profile |
| Chalked: critical enforcement outside agent | small host authority kernel |
| Chalked: tool success is not proof | authoritative state plus receipts |
| AlphaClaw: boundary outside reasoner | host bridge/controller outside OmegaLLM/OmegaJev |
| AlphaClaw: preserve upstream subject identity | pinned Omega plus documented derived modifications |
| AlphaClaw: bounded experiment/lifecycle | finite Jev turns, loopback RPC, external start/stop |
| AlphaClaw: evidence and non-claims | explicit verification-status vocabulary |
| BGI Commons discussions: hosted machine observability | local powered profile, external containment, independent stop |
| BGI Commons discussions: user vs infrastructure control | separate operator/provider/agent/world-authority roles |
| Provider diversity | adult-owned provider/model selector; capability change does not change authority |

### 5.1 Why OmegaLLM and OmegaJev are separate

Chalked established that an agent should not own the authority rule it acts
under. AlphaClaw reinforced that different causal roles should be separated at
inspectable boundaries.

StickerBook therefore separates:

- **OmegaLLM:** language mediation;
- **OmegaJev:** typed finite action selection;
- **authority kernel:** authorization;
- **OpenShell:** containment;
- **provider profiles:** credentialed inference egress;
- **responsible adult:** session-level provider/model enablement;
- **child:** interaction intent inside the permitted play surface.

No one of those roles is allowed to silently stand in for all the others.

### 5.2 Why the provider selector belongs to the adult

The multi-provider update is consistent with the lineage rather than an
exception to it.

A parent or operator may choose Sponsored ASI Cloud/MiniMax, Anthropic/Claude,
OpenAI, OpenRouter, ASI:One, or Off. That changes which configured inference
service OmegaLLM uses.

It does not change:

- who owns StickerBook state;
- what action keys Jev may select;
- which kernel actions are legal;
- whether OpenShell policy can expand;
- who owns the stop path.

This is precisely the distinction the prior work was converging on:

~~~text
better or different inference != more authority
~~~

---

## 6. Attribution and independence

StickerBook is independent research by Paul Carver Tiffany III.

Relevant prior work:

- **Chalked** — Paul Tiffany:
  https://github.com/PaulTiffany/chalked
- **AlphaClaw** — original project code credited in that repository to Paul
  Carver Tiffany III and Derek Tiffany:
  https://github.com/PaulTiffany/AlphaClaw/
- **BGI Commons** — external community/platform context:
  https://bgicommons.org/

Upstream Omega, OpenShell, Jev, PeTTa, model providers, and other dependencies
retain their own authorship and terms; see [NOTICE](../NOTICE) and
[TOOLS-AND-MODIFICATIONS.md](TOOLS-AND-MODIFICATIONS.md).

Participation in a community, use of an upstream tool, or technical
compatibility does not imply sponsorship, endorsement, employment, or shared
authority.

---

## 7. Research reading order

For someone trying to understand why StickerBook looks the way it does:

1. Chalked README.md, CHALKED_ARCH_SPEC.md, and SPRINT_BRIEF.md;
2. AlphaClaw README.md, RESEARCH.md, and PHILOSOPHY.md;
3. this lineage document;
4. [MEDIUM.md](MEDIUM.md);
5. [AGENT-INTERFACE.md](AGENT-INTERFACE.md);
6. [SECURITY.md](../SECURITY.md);
7. [TOOLS-AND-MODIFICATIONS.md](TOOLS-AND-MODIFICATIONS.md).

For someone reproducing StickerBook itself, the binding implementation details
remain in the StickerBook repository, not in the ancestor projects.

## HyperSprints support

StickerBook was made with support from [BGI Commons](https://bgicommons.org/) as part of its **HyperSprints series**. [StickerBook team page](https://bgicommons.org/teams/62).
