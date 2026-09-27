# Conversational Omega interface

StickerBook separates conversation, decision selection, and authority.

> **Omega talks. Jev chooses. The kernel decides.**

These are different interfaces and should remain different even if one model
or process eventually participates in more than one role.

## Conversation is not authority

The browser can send human language to the local conversational runtime through:

`POST /api/agent/converse`

The bridge validates the input and fixes the acting principal. The runtime
receives only:

- the validated text;
- the fixed browser principal id;
- a JSON scene view returned by the normal browser view.

It does **not** receive the authority-kernel object through this interface.

The response is language only. It does not mutate scene state and it does not
become a kernel command merely because Omega suggested something.

If a conversational Omega wants an in-world action, that action must enter the
same bounded path as other machine action: legal choices, typed selection,
host validation, and kernel adjudication.

## Creator drafts are also non-authoritative

`POST /api/creator/draft`

is a second non-authoritative seam. It can return a proposed page or sticker
asset description. Sticker drafts target asset schema v2, where one
StickerDefinition can contain an idle clip plus one or more behavior clips,
and each clip can contain one or many related image frames.

A creator draft does not install itself and cannot grant a behavior that the
world/kernel definition does not already permit.

## Voice-first child interface

Normal child-facing play has no persistent chat panel.

When a conversational runtime is connected, a responsible adult can enable
voice for the current browser session. Only then does a small push-to-talk
microphone appear on the active page.

The browser's speech-recognition implementation may use a browser/device speech
service. StickerBook therefore does not silently enable it. The responsible
adult panel states this explicitly.

The recognized text is sent to the local conversational endpoint. A returned
reply may be spoken with the browser's speech-synthesis facility.

## Text fallback

A small text interface exists only inside the responsible-adult/developer
panel. This provides:

- an accessibility/debug fallback;
- a way to test conversational Omega without occupying the child's page;
- an inspectable language path while voice behavior is developed.

It is not intended to become the primary child-facing interface.

## Default runtime

`web/agent_runtime.py` ships with `DisabledAgentRuntime`.

It advertises no creator or conversational capability and performs no network
access. GitHub Pages never receives this Python runtime at all; Pages remains
the mechanical static profile.

A future local Omega adapter should implement the same small interface rather
than reaching around the bridge into the kernel.
