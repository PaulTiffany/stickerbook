# StickerBook static assets

This directory is StickerBook's replaceable visual layer.

The browser reads `manifest.json` at startup. Asset files are ordinary data:
they do not define principals, ownership, agent tools, legal actions, or
authority.

## Canonical browser artboards

StickerBook now has explicit artboards for the browser surfaces we actually
render:

| Surface | Landscape | Portrait |
|---|---:|---:|
| title / cover | 1916 × 821 | 941 × 1672 |
| playable page | 1916 × 717 | 941 × 1574 |

The page dimensions deliberately exclude the bottom hotbar. The hotbar belongs
to browser UI, not to the governed page coordinate surface.

Cover art is allowed to fill/crop slightly (`slice`) because it is decorative.
Playable page art uses `meet`: the complete page coordinate surface stays
visible so child gestures and agent/Omega actions map onto the same bounded
world.

## Cover variants

The current cover uses:

```json
"cover": {
  "show_title": false,
  "alt": "StickerBook title page",
  "variants": {
    "desktop": {
      "src": "static/assets/cover.svg",
      "width": 1916,
      "height": 821
    },
    "landscape_phone": {
      "src": "static/assets/cover.svg",
      "width": 1916,
      "height": 821
    },
    "landscape": {
      "src": "static/assets/cover.svg",
      "width": 1916,
      "height": 821
    },
    "portrait": {
      "src": "static/assets/cover-vertical.svg",
      "width": 941,
      "height": 1672
    }
  }
}
```

The runtime chooses by the visible browser rectangle, not by device identity.
Desktop windows and landscape phones can therefore share art where their
geometry is similar.

Use `show_title: true` only when the artwork does not already contain the
StickerBook title.

## Page backgrounds

Each built-in page has a horizontal and portrait composition.

Naming convention:

```text
<page>.<ext>             # 1916 × 717
<page>-vertical.<ext>    # 941 × 1574
```

For example:

```text
farm.svg
farm-vertical.svg
```

Manifest entry:

```json
"farm": {
  "name": "The Farm",
  "summary": "Barns, fields and farm animals.",
  "thumbnail": "static/assets/pages/farm.svg",
  "alt": "Farm StickerBook page",
  "variants": {
    "landscape": {
      "src": "static/assets/pages/farm.svg",
      "width": 1916,
      "height": 717
    },
    "portrait": {
      "src": "static/assets/pages/farm-vertical.svg",
      "width": 941,
      "height": 1574
    }
  }
}
```

The current built-in page set is **Farm, Beach, Playground, and Space**.

### Supported formats

Page art does **not** need to be converted to SVG merely to work in
StickerBook. The static and local bridge paths support:

- SVG
- PNG
- JPEG / JPG
- WebP

Use whichever data format preserves the artwork appropriately. SVG wrappers
around embedded raster images may be useful for packaging, but they are not a
runtime requirement and can add unnecessary file size.

Page artwork is passive scenery. Governed StickerInstances remain separate
objects on top of it, and their normalized positions map across the landscape
and portrait variants.

## Child page-upload reframe contract

In powered local mode, a child-selected page image can be sent through the
optional page-image gateway to make the two canonical page variants. The
source may be SVG, PNG, JPEG/JPG, or WebP.

The gateway performs **two image edits against the original upload**. It does
not create the portrait image by stretching the landscape result. Because
OpenRouter image controls vary by model, StickerBook does not assume that a
provider-specific size parameter exists: the exact canvas is stated in each
fixed prompt and the returned image dimensions are checked mechanically. A
wrong-sized provider result is rejected rather than silently stretched,
cropped, or accepted.

Horizontal job:

```text
**Edit the uploaded image.**
Use the uploaded image as the direct reference and preserve the artwork, style, colors, subject matter, and overall composition as closely as possible.
**Do not create a new scene. Do not reinterpret the content.**
Only **reframe / extend / outpaint** the image so the final canvas is exactly 1916 × 717.
Keep the result **very similar to the original artwork**, with any newly added areas matching the same visual style and content naturally.
If needed, **expand the background and surrounding scene**, rather than stretching or distorting the image.
Avoid adding unrelated new objects, text, or design elements.
```

Portrait job:

```text
**Edit the uploaded image.**
Use the uploaded image as the direct reference and preserve the artwork, style, colors, subject matter, and overall composition as closely as possible.
**Do not create a new scene. Do not reinterpret the content.**
Only **reframe / extend / outpaint** the image so the final canvas is exactly 941 × 1574.
Keep the result **very similar to the original artwork**, with any newly added areas matching the same visual style and content naturally.
If needed, **expand the background and surrounding scene**, rather than stretching or distorting the image.
Avoid adding unrelated new objects, text, or design elements.
```

Generated filenames follow the same convention:

```text
<source-stem>.<provider-output-ext>
<source-stem>-vertical.<provider-output-ext>
```

Generation is non-authoritative and does not install a page into the governed
world. Saving/persistence remains a separate action.

The public GitHub Pages demo never sends an uploaded image to a model; it only
shows a local browser preview.

## Sticker assets

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

A clip may contain one frame or many related images. `frame_ms` controls
frame duration and `loop` controls whether the clip repeats. `motion`
optionally adds whole-sticker movement such as `hop`, `flutter`, or
`swim`.

Runtime legality still comes from the world/kernel StickerDefinition. The
manifest describes how an already-legal state looks; it does not grant that
state or action.

## Public deployment boundary

GitHub Pages copies this directory, but the workflow permits data-only asset
extensions only: SVG, PNG, JPEG, WebP, JSON and text. Python, JavaScript,
executables, credentials, Omega/Jev runtime material, and other privileged
files are not deployable through the asset path.

This directory is therefore an art/package boundary, not an execution
boundary.
