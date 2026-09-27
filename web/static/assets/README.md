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

Store sticker artwork under `stickers/`. Sticker files should have a
transparent background and should contain only the illustration itself.
StickerBook supplies the white die-cut paper border and shadow.

Example:

```json
"frog": {
  "src": "static/assets/stickers/frog.svg",
  "animation": "hop"
}
```

The key (`frog`) must match the StickerDefinition id exposed by the world.
Replacing `frog.svg` replaces its visual art without changing authority,
ownership, or behavior.

The manifest currently supports the visual source and a descriptive animation
name. Runtime legality still comes from the world/kernel definition, not from
this JSON file.

## Public deployment boundary

GitHub Pages copies this directory, but the workflow permits data-only asset
extensions only: SVG, PNG, JPEG, WebP, JSON and text. Python, JavaScript,
executables, credentials, Omega/Jev runtime material, and other privileged
files are not deployable through the asset path.

This directory is therefore an art/package boundary, not an execution boundary.
