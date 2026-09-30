# OpenRouter sticker refresh

Branch: `feat/minimax-sprite-refresh` (historical working name).

Refreshed **58 stickers / 232 pose files** using OpenRouter and supplied artwork.
The generated assets used **OpenRouter GPT Image 2**,
low quality setting, 1024px 2x2 sheets. Reported API usage cost including
consistency refinements: **$1.86151**. Failed calls supplied no usage cost.
Existing local OpenRouter credentials were used without printing or copying
them into artifacts. The sponsored ASI chat/vision lane was not altered.

## Pipeline and compatibility

All **304 originals plus the canonical manifest** were backed up byte-for-byte
under `assets/_backup_pre_minimax_refresh/`, preserving repository paths.
The machine-readable `assets/minimax_refresh_manifest.json` records every
original, backup, sheet, crop, prompt, model, outcome, and checksum.

The 80-sheet plan groups animals, nature, objects, toys, space, and people.
Each family group uses up to four distinct subjects, with separate sheets for
each pose. There are 79 successful sheet files and 45 archived first pose
attempts in `attempts/`. Matching family references improved consistency
after the initial style-only references caused design/color drift.

Crops remove edge-connected near-white backgrounds, discard disconnected
sheet guides, include bounded empty gutters to avoid cutting off extended
poses, and retain enclosed whites. A common bounding box across each
character's poses preserves placement. Final crops are transparent 256px PNGs.
Full 1024px sheets remain available for future higher-resolution processing.

Original SVG filenames, 144px viewBoxes, clip names, frame ordering, timing,
scale bounds, and manifest metadata remain unchanged. Each replaced SVG
contains its PNG, so there are no new runtime image URLs or code changes.
Reload the running app to discard cached originals; no agent/container
restart is required. `review/` contains contact sheets of staged outputs,
including rejected cameos: those rejected images are **not active**.

## Retained originals and failures

The other **18 cameo stickers / 72 poses** remain original. Generated sets did not
reliably preserve identity across poses; some even copied animals from the
style reference. `people_01_pose_01` failed twice, with HTTP 400 recorded on
retry. Other cameo outputs were rejected during visual review. Use verified
portrait references and dedicated human reference sheets for their next pass.

Retained IDs: anders-sandberg, aubrey-de-grey, ben-goertzel, david-eagleman, david-orban, david-pearce, eliezer-yudkowsky, fm-2030, giulio-prisco, hans-moravec, k-eric-drexler, martine-rothblatt, max-more, natasha-vita-more, nick-bostrom, paul-tiffany, ray-kurzweil, robert-ettinger, vernor-vinge.

All six backgrounds, landscape/portrait variants, cover art, and nine legacy
single-file sticker SVGs are unchanged. Backgrounds are separately inventoried
in the refresh manifest. No background refresh is proposed in this pass.

## Validation

- 304 original/backup SHA-256 pairs verified before replacement.
- 232 installed SVG raster payloads match staged crops and have real alpha.
- All 304 active image URLs served successfully by the running local app.
- Canonical manifest and all clip references remain unchanged.
- A replaced Butterfly SVG rendered successfully through CairoSVG.
- 523 web + 81 core + 40 Jev tests passed (**644 total**).
- Browser JavaScript syntax and Git whitespace checks passed.

No interactive browser session was available for a manual play check. Existing
HTTP, renderer, gesture, and authority regression tests passed; manual demo-video
review is still useful for subtle frame alignment/pose quality. These are
generated pose sequences, not guaranteed pixel-perfect hand-authored animation.

## Tools

Generation/postprocessing requires Python, Pillow, NumPy, and SciPy; these are
offline workflow dependencies, not new application dependencies. Preparation,
generation, cropping, reviewed replacement, validation, and this report each
have a script under `tools/`. Do not rerun staging over installed assets without
reviewing and reinstalling the resulting crops. No credentials belong in Git.

## Paul Tiffany supplied portraits

Paul supplied a transparent four-portrait sheet, installed without new inference.
The source is staged as `sheets/paul-tiffany_user_portraits.png`. Neutral maps
to `rest`, open hands to `explain`, thinking/notebook to `chalkboard`, and waving
to the legacy `poster` frame. Clip names and timings are unchanged; the supplied
poses do not depict a literal chalkboard or poster. Crops retain source alpha
and a common scale. Rejected generated Paul crops are archived in
`attempts/paul-tiffany_rejected_crops/`. Paul is now replaced; the retained-ID
list above reflects the earlier generation review. The other 18 cameos remain
original. All 304 live image URLs were reverified; no additional inference cost.
