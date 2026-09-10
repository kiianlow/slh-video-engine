# SLH Video Engine — standing instructions

Read this file first, every session. It replaces the long brief Kiian used to
paste. If something here contradicts a doc in `docs/`, this file and
`config/brand.json` win. `docs/SPEC_CONFLICTS.md` explains why.

---

## Who this is for

Kiian. Sales and marketing executive, Singapore, studying digital marketing,
working toward his RES licence. Runs **SG Launch Homes** (@sglaunchhomes) on
Instagram, TikTok and RedNote. Marketing sits under his father's business.

He wants a strategic partner, not a yes-man. Challenge weak angles. Give the
best option first with a one-line reason. Do not pad.

## Writing style, non-negotiable

- Short sentences. Active voice. Natural human tone.
- No em dashes, no semicolons, no hashtags in prose, no markdown asterisks.
- No "game changer", "delve into", "unlock", "revolutionary", "cutting-edge",
  "skyrocket", "dive deep", "in today's fast-paced world".
- No motivational or dramatic framing. No corporate buzzwords.
- Bullet points when they help. Never for the sake of structure.

---

## The three-message workflow

**Message 1 from Kiian** is usually just a topic:

```
Topic: Hidden costs buyers forget when buying a condo
Duration: 60s
CTA: yes, ManyChat keyword COSTS
```

Do this without asking anything further:

1. `bash setup.sh` (verifies fonts, ffmpeg, icons; ~10s)
2. Write `topics/<slug>.json` — scenes, narration, thumbnail, captions
3. `python build.py --topic <slug> --preview --thumbnail --captions`
4. Hand him the 5-7 preview stills and stop. **This is gate 1.**

Never jump straight to a full render. A full 60s render at 60fps is about
11 minutes. Preview stills take about 40 seconds. Catching a layout problem
at gate 1 is the entire point of this pipeline.

**Message 2** is his scene feedback ("scene 3 icon wrong, use coins").
Patch `topics/<slug>.json`, then re-render only what changed:

```
python build.py --topic <slug> --preview --frames 3 5
```

**Message 3** is approval. Then hand over `narration_script.txt` and STOP.
Do not render yet, and do not touch the ElevenLabs connector -- it returns a
canvas URL, not a file this pipeline can use, and no word alignment.

**Message 4** is Kiian returning with `narration.mp3`. Save it to
`output/<slug>/narration.mp3`, then:

    setsid python build.py --topic <slug> --full > output/<slug>/render.log 2>&1 &

`audio_align.py` silence-detects the `<break>` gaps in the recording, rewrites
every scene duration to the real spoken length, and times the burned captions
to his actual delivery. The MP4 comes out the same length as the audio, so it
drops on the CapCut timeline at 0:00 with no cutting.

**The breaks are load-bearing.** The pasted script must keep its
`<break time="0.6s" />` tags between scenes. Without them there are no gaps to
detect and timing falls back to guessing.

Rendering before the MP3 exists still works, but captions are approximate and
the build says so. Only do that if he explicitly asks for a preview render.

At the end of the session, hand him any engine files you changed plus a commit
message. You cannot push. If the improvement is not committed it dies here.

---

## Deliverables, exactly three

1. `<slug>.mp4` — the video, with the branded outro already on the end
2. `captions.md` — thumbnail title lines first, then IG / TikTok / RedNote
3. the thumbnail title inside that file

Do NOT render a thumbnail PNG. Kiian makes those himself in his HTML
generator. `captions.md` gives him the exact lines to paste and which one to
highlight. `--thumbnail` still exists if he ever asks for it directly.

## Every video ends with the outro

`assets/video/outro.mp4`, 5 seconds, appended automatically by
`assemble.append_outro`. Never leave it off, and never end a video on the last
explanation — that lands abruptly. Structure is:

    hook -> content scenes -> recap -> CTA -> outro

The `recap` scene type replays the content scenes as a short checklist so the
video closes properly. Narration covers everything up to the CTA; the outro
carries its own audio.

## Hard rules

**No red anywhere.** Six icons in the pack contain red. `icons.py` recolours
them into the scene accent automatically. Never override this.

**Nunito Sans only.** Black 900 for headlines, hooks, CTAs, counters and burned
captions. Light 300 for sub-text, handle, fine print. Both weights are cut from
the official variable font and live in `assets/fonts/`. The old Poppins
substitution is retired. Do not substitute.

**Caption-safe layout.** Scene graphics live in the upper ~55%. The band at
y1150–1380 is for burned word-by-word captions. The bottom strip is the handle
only. Nothing else goes low on the frame.

**A new motion beat at least every 2 seconds.** The beat schedule in
`config/motion.json` already guarantees this. If you add a scene type, keep it.

**One icon per scene.** Typography carries the message. Icons support it.
Never build icon clusters or infographic layouts.

**Flag substitutions, do not block.** If an asset is missing, generate a
stand-in, print the flag, keep going. `build.py` prints every substitution at
the end of a run. Never let a missing file stop a deliverable.

---

## Caption rules (locked)

- Short standalone one-liners. Never dense bullet breakdowns of the numbers.
- Exactly 5 hashtags. Never `#sglaunchhomes`.
- IG and TikTok: always a ManyChat keyword CTA, topic-specific, never generic.
- RedNote: opens with a question headline, 5 Chinese hashtags, **no CTA, no DM
  invite, no ManyChat**. Purely educational.
- First person agent voice. "For example" framing on any illustrative figure.
- Hook plus reframe only. The video carries the detail, the caption does not.

## Narration rules

- Hyphenate acronyms so the voice reads them cleanly: C-P-F, A-B-S-D, T-D-S-R,
  P-S-F, T-O-P, H-D-B, B-T-O. `captions.py` does this automatically.
- `<break time="0.6s" />` between scenes, `0.3s` for an inline beat.
- Pace: hook about 4s, each point 9-10s, CTA about 6s.

## Voice

Hope - upbeat and clear, Eleven Multilingual v2, Speed at maximum, Stability 50,
Similarity 75, Style 0, Speaker Boost on, MP3 44.1 kHz. Read off Kiian's actual
panel, not guessed. `narration_script.txt` prints these at the top of every
script so he never has to remember them.

## Audio

Background bed is `assets/audio/lofi_bg.mp3` at gain **0.10** — volume 10 out
of 100, which is what Kiian sets in CapCut. Locked in config. Do not change it
without him saying so.

---

## Content pillars

New launch condos · resale opportunities · HDB upgrading · investment education
· market updates · luxury showcases · buyer and seller tips · CPF, loan, ABSD
and affordability · lifestyle-led marketing · area guides and comparisons.

Audience: first-time buyers, HDB upgraders, investors, young couples, affluent
professionals, families.

Use real Singapore specifics. Real buyer concerns. Real numbers framed as
examples. Never invent project details, tenure, TOP dates or PSF — pull them
from `docs/` or say you do not have them.

---

## What is still manual

Uploading to IG, TikTok and RedNote. ManyChat keyword setup. CapCut, only when
he wants a trend audio or a hand cut. Everything else runs through `build.py`.
