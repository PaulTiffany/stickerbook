# StickerBook static assets

This directory is the replaceable visual layer for StickerBook.

The browser reads `manifest.json` at startup. Asset files are ordinary static
files and do not carry authority or executable agent behavior.

## Replace the cover

1. Put the replacement image in this directory, for example:
   `cover.jpg`.
2. Change `manifest.json`:

```json
"cover": {
  "src": "static/assets/cover.jpg",
  "show_title": false,
  "alt": "StickerBook cover"
}
```

Use `show_title: true` when the image does not already contain the StickerBook
title and the browser should draw the title layer over it.

## Add or replace a page background

Store page art under `pages/`. The farm page currently uses:

```json
"pages": {
  "farm": {
    "src": "static/assets/pages/farm.svg",
    "thumbnail": "static/assets/pages/farm.svg",
    "alt": "Sunny farm with barn, tree, pond and fence"
  }
}
```

A PNG, JPEG, WebP or SVG can be used. Page artwork is passive scenery. Governed
StickerInstances remain separate objects on top of the background.

## Add or replace a sticker

A sticker is a **visual package**, not necessarily one image.

Store sticker artwork under `stickers/`. Files should have transparent
backgrounds and contain only the illustration itself. StickerBook supplies the
white die-cut paper border and shadow.

Manifest v2 represents each StickerDefinition as named clips:

```json
"frog": {
  "default_clip": "idle",
  "clips": {
    "idle": {
      "frames": [
        "static/assets/stickers/frog.svg"
      ],
      "loop": false
    },
    "hop": {
      "frames": [
        "static/assets/stickers/frog/hop-01.png",
        "static/assets/stickers/frog/hop-02.png",
        "static/assets/stickers/frog/hop-03.png"
      ],
      "frame_ms": 110,
      "loop": true,
      "motion": "hop"
    }
  }
}
```

A clip may contain one frame or many related images. Multi-frame clips are
cycled by the browser. `frame_ms` controls frame duration and `loop`
controls whether the clip repeats. `motion` optionally adds a whole-sticker
movement such as `hop`, `flutter`, or `swim` while the image frames change.

The current built-in clips use one frame plus whole-object motion, but the
schema is already ready for frame-by-frame animation produced by Sticker Maker.

The key (`frog`) must match the StickerDefinition id exposed by the world.
Replacing the files changes visual art without changing authority, ownership,
or legal actions.

Runtime legality still comes from the world/kernel StickerDefinition. The
manifest describes how an already-legal state looks; it does not grant that
state or action.

## Public deployment boundary

GitHub Pages copies this directory, but the workflow permits data-only asset
extensions only: SVG, PNG, JPEG, WebP, JSON and text. Python, JavaScript,
executables, credentials, Omega/Jev runtime material, and other privileged
files are not deployable through the asset path.

This directory is therefore an art/package boundary, not an execution boundary.
