# SLH_MASTER.md — patch for burned-in captions (v2.1)

Apply these two edits to keep the master in sync with the skill.

---

## Edit 1 — Section 4, RECURRING RULES

REPLACE this line:

> - Keep all graphics/text **smaller and in the UPPER ~55%** of the frame. Leave mid-to-lower clear for CapCut captions. No burned-in graphics low on screen.

WITH:

> - Keep all scene graphics/text **in the UPPER ~55%** of the frame. The lower-middle band (~y 0.58H) is the **burned-in word-by-word caption zone** — keep it clear of scene graphics. Only the very bottom handle strip stays empty.
> - **Captions are burned into the render**, word by word, all-caps white with a soft low-opacity shadow (no hard outline), Nunito Sans Black 900. One word at a time, pop-in per word. No longer hand-added in CapCut.

---

## Edit 2 — Standard video deliverable bundle

REPLACE item 1 and ADD item 5:

> 1. MP4 render **with burned-in word-by-word captions** (module: `slh_captions.py`)
> 2. ElevenLabs narration script with `<break>` tags …
> 3. IG/TikTok caption + RedNote Mandarin caption
> 4. Pixabay background audio — minimal modern underscore (NOT lo-fi)
> 5. **Caption timing source** — state which was used:
>    - **ElevenLabs word alignment** (best, zero drift — export the alignment JSON from the VO render)
>    - SRT file
>    - Auto-distributed from script (fallback, flag as approximate)

---

## Caption timing — production note

The pipeline renders the MP4 silent and adds VO in CapCut. For exact captions, flip the order:
generate the ElevenLabs VO first → export its word alignment → render with `CaptionTrack.from_elevenlabs(...)`.
No alignment yet → render with `from_scenes(...)` and flag the timing as approximate.
