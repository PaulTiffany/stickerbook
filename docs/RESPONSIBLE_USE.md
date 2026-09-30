# Responsible-adult supervision and privacy

<img src="../assets/_generated_sprite_refresh/cropped/teddy-bear/rest.png" alt="Teddy bear sticker" width="140">

**Children must use StickerBook's AI features with a responsible adult supervising.**
This is an experimental research prototype. It is not a babysitter, professional
adviser, educational assessment, emergency resource, or certified child-safe
service. The authority kernel limits what agents may change; it cannot guarantee
that a reply or generated picture is truthful, appropriate, or harmless.

## Before enabling AI

- Review the configured providers' privacy, age, account, and billing terms.
  The adult operates credentials and decides whether a service is suitable.
- Review spoken replies and generated images. Explain that AI can make mistakes.
  Stop a session, disable conversation, or close the page if anything is upsetting.
- Keep names, addresses, school details, contact information, passwords,
  identifying child photos, and other sensitive information out of prompts and uploads.
- Enable the microphone only with the child's and responsible adult's understanding.
  Browser/device speech recognition may use platform services; speech synthesis
  may also depend on the browser/device.

## What leaves the computer and what remains

Public GitHub Pages is a mechanical demonstration with no provider/model access.
Uploads there are browser-local previews. Powered local mode may send text,
bounded scene context, and page-image observations to the selected inference
provider. Creation requests may send descriptions and reference artwork to a
separate image service. Provider handling is governed by that service's terms;
localhost does not mean all inference happens on the device.

OmegaLLM and OmegaJev each have a separate native memory store in Docker-managed
volumes. These may retain bounded conversations, replies, accepted experiences,
and teaching feedback. Recreating or stopping containers does not erase those
stores. There is no account-based separation or polished parental deletion UI;
do not treat one shared local installation as isolated child accounts. An adult
operator should manage retention and backups deliberately. In-memory page worlds
and pattern libraries have different lifetimes from durable agent memory.

## Control and limits

An adult controls providers, costs, credentials, and process shutdown. A child
controls page play and can interrupt a sticker by grabbing it, stopping it, or
leaving the page. Neither role's language output gains kernel authority. The
adult/developer panel is an interface boundary, not authenticated parental access.

Restricted ordinary Docker is **local powered development**, not a production
deployment or OpenShell-equivalent containment. Role containers hold real provider
credentials and have direct provider egress. Do not expose the bridge or agent
ports publicly. See [deployment restrictions](DOCKER_POWERED_LOCAL.md) and
[the binding security model](../SECURITY.md).

No human-subject outcome study, broad safety certification, guaranteed behavior
learning, or guaranteed organic movement is claimed. Native memory and feedback
can shape future choices; they do not train model weights or expand permissions.
