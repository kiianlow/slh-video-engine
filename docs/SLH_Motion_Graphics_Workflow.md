# SG Launch Homes — Motion Graphics Video System

Drop this file into the Project so every new chat reproduces the same style. Each video request runs through this system and returns the same four outputs.

---

## 0. The deliverable set (every video returns all four)

1. The video — 1080×1920 MP4, ~60s, silent (audio added in CapCut).
2. ElevenLabs narration script — plain text with break tags and voice settings.
3. Captions — one for Instagram + TikTok (shared), one for RedNote (Mandarin).
4. Background audio pick — Pixabay search recipe and a top recommendation.

---

## 1. Locked style (do not change between videos)

**Canvas:** 1080×1920, 30fps, H.264, yuv420p, faststart.
**Duration model:** Hook 4s → content scenes 10s each → CTA 6s. Five content scenes = 60s. Adjust scene count, keep the per-scene seconds.

**Type system — Poppins (standard, locked):**
- Headlines, counters, WhatsApp number, block labels → **Poppins Bold**.
- Kicker, sub-text, handle, captions, fine print → **Poppins Light**.
- Poppins is the chosen font. Do not substitute (Manrope is no longer planned).

**Palette (brand core):**
- Background `#E8E0D0` · Ink `#3D2B1F` · Secondary `#5C3D2E` · Card `#F4F0E8` · Handle `#8B6355`.
- **No red, ever.**

**Accent rotation** (one muted accent per scene, for colour-coded life):
- Terracotta `#C07B4F` · Teal `#5E8C86` · Gold `#C7A24B` · Clay `#C07B4F` · Dusty blue `#6E8CA8` · Sage `#8A9A6B`.
- The accent drives: scene icon fill, kicker, card left-bar, underline, timeline fill, the "AT TOP" block, and the particle colour.

**Layout (caption-safe):** All elements sit in the upper two-thirds. The lower band (~last 350px) stays clear for the user's own captions. Counter top, icon hero centre, headline, sub-text card, optional graphic, handle near the lower-third line.

**Motion system** (a new beat at least every ~2s):
- Continuous: accent particles drifting up, icon float + sway, background blob drift, film grain.
- Entrance stagger: kicker → icon scale-in (spring) → headline slide-in from left → card fade with accent-bar wipe.
- Pulse rings expand from the icon at 0, 1.5, 3.5, 6, 8.5s.
- Headline shine sweep at 2.2, 4.4, 6.6, 8.8s.
- Icon spring bounce at 3, 5.5, 8s · icon wiggle at 4.5, 7.5s · counter pop at 3, 6, 9s.
- Scene-specific: NOW→TOP timeline draw (date scenes), sequential payment blocks (payment scenes).
- Transitions: 0.22s cross-dissolve between scenes. No hard cuts.

---

## 2. Asset pipeline

**Source of truth:** the Project files — `brand-guidelines.md`, `SLH_Brand_Framework.md`, `motion-icons-system.md`, and the example carousels. Pull tenure/TOP/size facts and tone from there. Never invent project details.

**Icons:** the uploaded Streamline icon pack (`motion_graphics_elements_and_icons.zip`).
1. `svg2png.py` parses the SVG paths (fills + strokes) and rasterises with matplotlib.
2. `recolor_icons.py` maps each icon into the scene accent as a 3-stop duotone — dark brown outline, accent body, pale accent fill. Result: line-art icons that match the warm brand and stay light.
3. One icon per scene, matched to the caption.

**Icon map used so far:** house → property/hook · ruler (Scale-Horizontal) → size · building → floor/PSF · handshake → developer · clock → TOP date · hand+cash → payment · bookmark → save/CTA · chat bubble → DM. Extend from the pack as topics change.

---

## 3. Build engine

Files in this folder:
- `svg2png.py` — SVG → PNG rasteriser (offline, no cairo needed).
- `recolor_icons.py` — brand-duotone recolour per scene accent.
- `render.py` — the frame-by-frame compositor + ffmpeg encode.

Run order in the Claude environment:
```
python3 svg2png.py <IconNames...>      # rasterise needed icons
python3 recolor_icons.py               # recolour to scene accents
python3 render.py                      # encode MP4 to outputs
```

---

## 4. Scene config (the only thing that changes per video)

Edit the `QS` list in `render.py`. Each entry: `(icon_key, HEADLINE, sub-text)`.
```
QS = [
  ("size",  "THE SHOWFLAT'S ACTUAL SIZE",   "Ask about voids, not just strata area"),
  ("floor", "WHAT FLOOR IS THIS, AND THE PSF?", "PSF changes with floor and facing"),
  ...
]
```
Rules: headline ≤ ~5 words, ALL CAPS, fits 2 lines. Sub-text one short line. Accent auto-assigned per scene. Hook title and CTA copy live in their own scene functions.

---

## 5. Output formats

### 5.1 Video
Silent MP4 at the spec above. Hand off to CapCut for voiceover + music + SFX.

### 5.2 ElevenLabs narration
- Plain text, one paragraph per scene, separated by break tags.
- Use `<break time="0.6s" />` between scenes, `<break time="0.3s" />` for in-line beats.
- Spell acronyms for clean read: `PSF` → "P-S-F", `TOP` → "T-O-P".
- Voice: **Adam** — Stability 67, Similarity 75, Style 0, Speaker Boost on.
- Pace target: hook ~4s, each point ~9–10s, CTA ~6s. Keep sentences short.

### 5.3 Captions
**Instagram + TikTok (shared, one caption):**
- Hook line → 2–3 value lines → "Save this" → ManyChat keyword CTA → follow line.
- ManyChat keyword is topic-specific (e.g. `SHOWFLAT`, `TDSR`, `LEASE`), never generic.
- Max 5 hashtags.
- Grant/education-only posts: engagement, no ManyChat CTA.

**RedNote (separate, Mandarin):**
- `标题：` keyword-rich title line.
- Body in Mandarin, numbered points, emoji light.
- Direct DM CTA (no ManyChat on RedNote).
- Localised hashtags.

### 5.4 Pixabay background audio
Selection criteria (locked):
- No vocals · 80–95 BPM · warm, minimal, soft piano or light lo-fi beat · ≥60s · loopable.
- Mood: focused and trustworthy, not hype, not lounge.
- In CapCut keep music at 15–20% under the voiceover.
How to pick: pixabay.com/music → filter Lo-fi / Beats, mood Calm or Relaxing → search `lofi study calm` or `minimal warm piano` → sort by most downloaded → preview for a soft, steady track with no drop. Verify it is free for commercial use.

---

## 6. Requesting edits

Re-prompt in plain language; the engine is parametric. Examples that map cleanly:
- "Change Q3 headline to X and the sub to Y" → edit `QS`.
- "Swap the payment icon for a credit card" → change icon key + re-run recolour.
- "Make the teal warmer / use gold on Q2" → edit `ACC`.
- "Move everything up 80px" → change `UP`.
- "Slower pacing / more motion" → adjust the beat schedules.
- "Add a 6th question" → append to `QS` (adds 10s).

---

## 7. Pre-publish checklist
- [ ] Background `#E8E0D0`, no red anywhere.
- [ ] One accent per scene, from the rotation.
- [ ] Headlines ExtraBold, support text Light.
- [ ] One icon per scene, brand-duotone, matched to copy.
- [ ] Lower band clear for captions.
- [ ] Hook lands in the first 3s.
- [ ] Handle on every scene, CEA No. R011448D on the CTA only.
- [ ] A new motion beat at least every 2s.
- [ ] All four outputs delivered.
