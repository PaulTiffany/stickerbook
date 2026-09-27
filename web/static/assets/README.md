# StickerBook static assets

This directory is the replaceable visual layer for StickerBook.

The browser reads `manifest.json` at startup. Asset files are ordinary static
files and do not carry authority or executable agent behavior.

## Replace the cover

Manifest v3 supports orientation-specific visual variants.

A landscape-only cover is valid and will always be shown in full. On a portrait
screen it will be letterboxed rather than cropped:

```json
"cover": {
  "show_title": false,
  "alt": "StickerBook cover",
  "variants": {
    "landscape": {
      "src": "static/assets/cover-landscape.svg",
      "width": 1672,
      "height": 941
    }
  }
}
```

If you make a dedicated portrait composition, add it without removing the
landscape version:

```json
"cover": {
  "show_title": false,
  "alt": "StickerBook cover",
  "variants": {
    "landscape": {
      "src": "static/assets/cover-landscape.svg",
      "width": 1000,
      "height": 640
    },
    "portrait": {
      "src": "static/assets/cover-vertical.svg",
      "width": 941,
      "height": 1672
    }
  }
}
```

StickerBook automatically selects the portrait asset after phone rotation when
one is available. If it is not available, the landscape artwork remains fully
visible instead of being cropped.

Use `show_title: true` when the image does not already contain the StickerBook
title and the browser should draw the title layer over it.

## Add or replace a page background

Page backgrounds use the same orientation-variant structure:

```json
"pages": {
  "farm": {
    "name": "The Farm",
    "summary": "Barns, fields and farm animals.",
    "thumbnail": "static/assets/pages/farm.svg",
    "alt": "Farm StickerBook page",
    "variants": {
      "landscape": {
        "src": "static/assets/pages/farm.svg",
        "width": 1000,
        "height": 640
      }
    }
  }
}
```

A future portrait composition can be added as:

```json
"portrait": {
  "src": "static/assets/pages/farm-portrait.svg",
  "width": 640,
  "height": 1000
}
```

A PNG, JPEG, WebP or SVG can be used. High-quality page art is intentionally
allowed to remain large. StickerBook uses `meet` fitting so the complete
native composition stays visible. Portrait assets are therefore an artistic
upgrade, not a requirement for correctness.

Page artwork is passive scenery. Governed StickerInstances remain separate
objects on top of the background, and their normalized positions map across
landscape and portrait variants.

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
