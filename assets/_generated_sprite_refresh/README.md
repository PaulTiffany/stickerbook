# Sticker library refresh

Branch: `feat/minimax-sprite-refresh` (historical working name).

All **76 stickers / 304 pose files** are refreshed: 57 non-cameo stickers
generated with OpenRouter GPT Image 2, ten user-supplied cameo sheets, and nine
referenced cameo sheets generated with the built-in image_gen tool.

## Generation and review

OpenRouter used low quality, 1024px 2x2 family sheets, up to four subjects per
sheet with separate sheets per pose. Reported usage including consistency
refinements was **$1.86151**. Failed calls supplied no usage cost. There are
Generation history records the original attempts and refinements; only the
79 source sheets used by active artwork remain in the working tree.
The nine final built-in sheets each contain four poses of one person, using
that person's portrait as identity reference and the supplied David Orban
sheet as style reference. The built-in tool exposes neither model name nor
billing cost; these generations are not attributed to MiniMax or OpenRouter.
No credentials are included in artifacts; the ASI lane is unchanged.

The final nine are Anders Sandberg, David Pearce, FM-2030, Giulio Prisco,
Hans Moravec, K. Eric Drexler, Martine Rothblatt, Robert Ettinger, and Vernor
Vinge. Full prompts, cell mappings, identity-reference URLs, settings, paths,
checksums, and outcomes are in `assets/sprite_refresh_manifest.json` under
`builtin_generated_sheets` and the corresponding pose records. Historical
photos vary in resolution, especially Robert Ettinger's small professor
portrait. Referenced illustration does not guarantee exact portrait likeness.
Downloaded identity photos are local workflow inputs, not shipped assets.

All full sheets are in `sheets/`; individual transparent 256px PNGs are in
`cropped/<id>/`. Review contact sheets include `review/builtin-cameos.png`
and `review/supplied-cameos.png`. Rejected/superseded image binaries have been removed. Original failed and
rejected generation records remain in the manifest as pipeline history;
there are now no retained original pose files.

## Compatibility and recovery

All superseded originals, backup copies, rejected sheets/crops, unused review
images and nine legacy single-file sprites have been removed: **471 files,
68,977,905 bytes (~65.8 MiB)**. Git history provides recovery. Original SHA-256
checksums and historical paths remain in `assets/sprite_refresh_manifest.json`;
retention flags distinguish removed artifacts from retained files. Deleting
tracked files reduces checkout/deployment size, not existing Git history size.
Original SVG paths, `-72 -72 144 144` viewBoxes, clip names, ordering, timing,
scale bounds, and canonical manifest metadata remain unchanged. Active SVGs
embed their transparent PNG, adding no runtime image URLs or dependencies.
No application runtime code, Docker configuration, cover, page backgrounds,
landscape/portrait variants, or nine legacy single-file SVGs changed.
Reload the app to clear cached original sprites; no container restart is needed.

Cropping preserves enclosed light clothing and source alpha, removes background
and stray components, and uses a common scale across each portrait's four poses.
Giulio's white borders touch near the lower gutter: a reviewed quadrant split
separates them without cutting facial features or props. These are illustrated
pose sequences, not pixel-perfect hand-authored frame animation.

## Supplied artwork mappings

Ten supplied sheets including Paul were installed without regenerating them.
Paul's neutral/open hands/thinking notebook/wave map to the existing
rest/explain/chalkboard/poster frames; legacy names are retained even where
props differ. Ray's supplied sheet has no thinking pose: his calm portrait
is reused for think, and celebration is staged separately as
`cropped/ray-kurzweil/celebration-unused.png`. Aubrey rest and Nick rest use
their calm open-palms poses; Ben think uses his raised-finger idea pose.
Full per-person mappings and source provenance remain in the manifest.

## Validation

- 304 provenance records and the original canonical-manifest hash verified.
- All 304 installed SVG payloads match their staged transparent 256px PNGs.
- All 304 active image URLs resolve through the running local app.
- Canonical manifest, clip references and SVG viewBoxes remain unchanged.
- 523 web + 81 core + 40 Jev tests passed (**644 total**).
- Browser JavaScript syntax and Git whitespace checks passed.

No interactive browser play check was performed. HTTP and renderer/gesture/
authority regressions cover compatibility; manual demo review remains useful
for subtle pose alignment. The generated contact sheets were visually reviewed.

## Tools

Offline preparation/generation/cropping/installation/validation tools are in
`tools/`. They require Python, Pillow, NumPy and SciPy, not new app dependencies.
`sprite_refresh_paths.py` centralizes the manifest location.
`prepare_sprite_refresh.py` prepares new inventories. The one-time installers
require original backups: restore those from Git before rerunning a replacement.
`install_builtin_cameos.py` takes reviewed sheet specs plus identity-reference
metadata and preflights all originals/crops before replacing files. Do not
rerun old staging over installed crops without reviewing the outputs.
