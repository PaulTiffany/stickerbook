# Submission review — September 30, 2026

<img src="../assets/_generated_sprite_refresh/cropped/robot/rest.png" alt="StickerBook robot" width="130">

## What to review

- [Cross-Modal Witnesses — compiled paper](../paper/cross_modal_witnesses/main.pdf)
  and [source/evidence bundle](../paper/cross_modal_witnesses/README.md).
- [Published music/demo video](https://youtu.be/vpu4tmhyj04).
- [Public mechanical book](https://paultiffany.github.io/stickerbook/) — no live AI.
- [Actual runtime evidence](../video/data/proof.json), its
  [reproducibility record](../video/README.md), and the paper's
  [conservative observed-evidence projection](../paper/cross_modal_witnesses/experiment/runtime_evidence/README.md).
- [Current Docker setup and restrictions](DOCKER_POWERED_LOCAL.md),
  [security model](../SECURITY.md), and [responsible-use guide](RESPONSIBLE_USE.md).

## Deployment disclosure

**As of submission, the upstream OpenShell/WSL deployment issue is unresolved.**
OpenShell has not been qualified as the running StickerBook containment layer
on this host. Its pinned configuration and archived launchers remain in the
repository as the desired hardened target; no production OpenShell claim is made.
OpenShell troubleshooting is stopped for this tranche.

The working, previously live-qualified local graph is:

```text
browser → host bridge / StickerBook authority kernel
             ├─ localhost OmegaLLM — restricted Docker container
             └─ localhost OmegaJev — separate restricted Docker container
```

Containers run non-root with dropped capabilities, no-new-privileges, bounded
resources, read-only roots, separate networks and role-specific memory volumes.
Ports bind only to localhost. Neither receives the repository, Docker socket,
host-network access, kernel object, or world-mutation authority.

This is **LOCAL POWERED DEVELOPMENT**, not OpenShell-equivalent containment or
a production child-facing service. Real credentials are injected into the
relevant containers and direct provider egress is allowed. Docker does not
reproduce OpenShell's credential substitution, executable-bound egress policy,
or network mediation. The host kernel remains the final mutation authority.

Prior successful runs are dated evidence, not a promise that services are
currently running after a restart. Docker Desktop alone does not start the host
bridge or inject newly set credentials into an existing container.

## Evidence boundaries

The music video combines asset choreography with explicitly labeled real
runtime observations. Choreographed arcs are not evidence of a model's chosen
course. Observed captures establish accepted direct-control receipts, child
interruption, page-local state restoration, and a bounded language goal within
their recorded scope. They do not establish OpenShell containment, complete
cross-page delayed-response injection, or a finished perceptual observer study.

The paper includes formal results, proposed methods, 14 synthetic calibration
traces, and four separately labeled positive runtime observations. Synthetic
violations are fixtures, not claims that the live kernel accepted violations.
There are no participant results, broad safety certification, or trained model
weights. Child feedback changes advisory native memory strengths and recall.

Children's AI use requires a responsible adult supervising. Localhost does not
mean inference or browser speech processing stays on the device.

## HyperSprints support

StickerBook was made with support from [BGI Commons](https://bgicommons.org/) as part of its **HyperSprints series**. [StickerBook team page](https://bgicommons.org/teams/62).
