# I'm Upping My P(HOP) — StickerBook music video

A deterministic 1920×1080 sticker-paper video driven by the supplied **179.840 s
WAV**. All six page backgrounds, cover and upgraded sprites are read from the
application's canonical asset manifest. Nothing in the app or Docker runtime
is changed. No model or network calls occur while rendering.

## Reproduce

Install FFmpeg (including ffprobe) and Python 3.13, then:

```powershell
python -m pip install -r video/requirements.txt
python video/render.py --stills
python video/render.py
python video/verify.py
```

Output: `video/output/stickerbook-phop.mp4` (ignored generated artifact).
Preview: `python video/render.py --from 47.22 --to 61.56 --output video/output/chorus-preview.mp4`.
Contact sheet: `video/output/contact-sheet.png`. The frame renderer accepts
arbitrary master time, so stills and export share exactly the same scene code.
Artwork transforms, confetti and trails are deterministic functions of time.
Fonts and licenses are included to avoid machine-dependent typography.
`--workers 2` renders two frames concurrently with an eight-frame queue cap;
the frame order/visuals are unchanged and no simulation state is shared.
Open `video/review.html` for local playback and buttons to the proof/chorus cues.
`data/inputs.json` records 326 source/input hashes and the toolchain; regenerate
with `snapshot_inputs.py` only when deliberately changing a source input.

Export uses libx264 CRF 18, 1920×1080, nominal 30 fps, yuv420p, AAC 320 kb/s and
fast-start MP4. `exact_clock.py` adjusts only the final sample's duration and
MP4 track/edit durations: 179.840 seconds is not an integer number of 30 fps
frames. No visual/audio fade or material is appended after the master clock.
The WAV is never regenerated or substituted; its SHA-256 is in `data/audio.json`.

## Timing and words

`lyrics.txt` preserves Paul's supplied lyrics as the sole authoritative text.
Speech recognition is **only a timing aid**; recognized words never become the
video's lyric captions. `analyze.py` measures positive spectral-flux onsets,
estimates tempo/phase and aligns matching tokens from a local Whisper pass.
The measured beat estimate is approximately **103.04 BPM**; beat pulses govern
motion accents and matched vocals govern lyric picture cues.

`data/timeline.json` contains every explicit lyric/scene cue and timing
confidence. Music ASR is imperfect, especially the post-chorus and unmatched
tail. `build_timeline.py` makes those visual windows explicit instead of
stacking unmatched words at one timestamp. These windows are editorial cues,
**not verified word-level karaoke alignment**. Low-confidence lines are not
printed as purported synchronized lyrics. The supplied full text is retained
even where the recording/transcription cannot establish an exact vocal match.
The closing HOP graphic hits the final visual window and hard-ends with the WAV;
the precise final vocal onset remains an editorial review point.

Optional regeneration: install `faster-whisper`, then run `transcribe.py`,
`analyze.py`, `build_timeline.py`. The current local alignment model/dependency
cache is outside committed inputs. Rendering only needs saved JSON; model
weights and speech recognition are not application dependencies. Listen/review
uncertain cue windows before changing their timing, never replace supplied
lyrics with ASR guesses.

## Film and proof

Opening cover fold, world selection and sticker sheet lead into frog hops,
bird launches, drag/drop, escaping curve, page repair and brief cameo punchlines.
Choruses use recurring frog/bird heroes, beat-pulsed type and musical P-HOP/
P-DOOM meters. The architecture verse compresses language into a finite legal
choice; the shell bridge distinguishes the desired hardened runtime from
working restricted local Docker. The ending returns to six independent worlds.

Four proof moments are reconstructed from **actual live runtime data** in
`data/proof.json`, not fictional receipts or an app screen recording:

1. OmegaLLM: “Make the butterfly flutter.” produced a bounded animate/flutter
   goal, successful reply and a live activity in 5.49 seconds.
2. Direct double-tap: child gesture to OmegaJev with `translatedBy: null`,
   finite offered keys, animation and positional receipts accepted by the host.
3. Child hand: active autonomous movement was stopped with `child-grabbed`,
   then an ordinary child move was accepted. No autonomous retry is portrayed.
4. Page isolation: captured Farm state → empty Space → restored Farm; the Farm
   butterfly was absent from Space. This is host state proof, not a claim that
   a delayed live provider request was injected across pages during capture.

The proof sequence is labeled **real runtime trace / time compressed**. Position
endpoints come from accepted kernel receipts. Browser-style interpolation is
presentation only. Other musical hops, curves, pose changes and cameo motion
are editorial choreography, not evidence that Jev selected those exact paths.
Discrete learned-pattern scenes illustrate existing advisory memory; they do
not claim continuous child-taught style learning or an unrecorded live recall.

`capture_proof.py` creates isolated host worlds and calls the existing loopback
OmegaLLM/OmegaJev containers. It preserves the child's running bridge state.
It captures no credentials or provider logs. Re-capturing is optional and may
produce different model choices; the committed proof JSON makes the film
reproducible. The current trace is noticeably linear: the film does not present
its musical swoops as a solved live motor/learning capability.

Kernel authority remains: browser → host bridge/kernel → two separate localhost
agents. OmegaLLM provides meaning; OmegaJev selects host-owned offered keys;
every mutation needs kernel acceptance. Public Pages remains mechanical.
OpenShell is the hardened target, **not the active runtime captured here**.
Restricted Docker has direct provider egress and is not OpenShell-equivalent.

## Inputs and credit

- Song, Suno lyrics and WAV supplied by Paul Tiffany: “I'm Upping My P(HOP)”.
- Cover, six worlds and 76-sticker library: this StickerBook repository.
- Supplied Jev logo and Omega GitHub screenshots: Paul-provided input files.
  Screenshots are retained as supporting source material; the main edit favors
  readable diagrams and actual structured runtime evidence over screenshots.
- Docker logo: supplied `Docker-svgrepo-com.svg`, source:
  https://commons.wikimedia.org/wiki/File:Docker-svgrepo-com.svg
- Fredoka and JetBrains Mono: Google Fonts, SIL Open Font License files in
  `input/fonts/`. Fonts are used under their included licenses.
- Technical inspiration: [mexicat/pdoom-video](https://github.com/mexicat/pdoom-video)
  and [JohnHeibel/PDoomVideo](https://github.com/JohnHeibel/PDoomVideo): deterministic
  song-time rendering, measured edit data, still/contact-sheet review and offline
  FFmpeg export. This implementation is original; no source code or visual
  material was copied from those projects.

`verify.py` checks exact duration, codecs, resolution, 326 input hashes, timing,
proof authority and deterministic frames, decodes the finished MP4, and compares
five decoded video frames against the renderer (allowing normal H.264 loss).
Human editorial review remains appropriate for music/lyric alignment and taste.
