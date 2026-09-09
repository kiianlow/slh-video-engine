# SLH Video Engine

Production pipeline for SG Launch Homes short-form property videos.
1080x1920, 60fps, Nunito Sans, burned word-by-word captions, thumbnail and
social captions out of the same run.

## Start a session

```bash
git clone <this repo> slh && cd slh
bash setup.sh
```

Then tell Claude the topic. It writes `topics/<slug>.json` and runs the build.

## Commands

```bash
python build.py --topic hidden-costs --preview              # 1 still per scene, ~40s
python build.py --topic hidden-costs --preview --frames 3 5 # re-render 2 scenes only
python build.py --topic hidden-costs --thumbnail
python build.py --topic hidden-costs --captions             # narration script + social captions
python build.py --topic hidden-costs --full                 # full render + audio mux
python build.py --topic hidden-costs --full --draft         # 30fps, half the time
python build.py --topic hidden-costs --all
```

Full renders are long. Detach them:

```bash
setsid python build.py --topic hidden-costs --full > output/hidden-costs/render.log 2>&1 &
tail -f output/hidden-costs/render.log
```

Render time, measured: **0.19s per frame**. A 60s video is about 11 minutes at
60fps, 5.6 minutes at 30fps.

## Voiceover

Drop these in `output/<slug>/` before `--full`:

- `narration.mp3` — ElevenLabs render, George 55/80/5, boost on
- `alignment.json` — word alignment, if ElevenLabs returns it

With alignment, caption timing is exact. Without it, timing is auto-distributed
from the script and the build prints a warning. Never ship approximate timing
without knowing it is approximate.

## Structure

```
CLAUDE.md              standing brief — read first every session
config/brand.json      single source of truth: canvas, type, palette, audio, voice
config/motion.json     easing, beat schedule, icon moves
config/icons.json      scene key -> icon file, red flags, fallback shapes
assets/fonts/          Nunito Sans Black 900 + Light 300, cut from the variable font
assets/icons/          drop the 22-icon pack here (see docs/SPEC_CONFLICTS.md)
assets/audio/          lofi_bg.mp3, played at gain 0.10
assets/brand/          logo badge, brand logo, font specimens
engine/motion.py       easing curves and animation primitives
engine/icons.py        icon loader, red recolour, Fluent-style fallback generator
engine/scenes.py       frame compositor: hook, point, cta
engine/captions.py     burned word-by-word captions + narration script builder
engine/thumbnail.py    Python port of the HTML thumbnail generator
engine/assemble.py     ffmpeg encode and audio mux
skills/                the skills this workflow uses, vendored
docs/                  original project specs, reference carousels, conflict log
topics/                one json per video — the only file that changes per topic
output/                renders, previews, deliverable bundles
```

## Adding a video

Write `topics/<slug>.json`. Scene schema:

```json
{
  "type": "point",             // hook | point | cta
  "kicker": "POINT 01",
  "icon": "card",              // key from config/icons.json
  "icon_move": "card_flip",    // spin360 | card_flip | coin_flip | float_bob
                               // | drop_squash | orbit | morph_swap | pulse_scale
  "headline": "Buyer's stamp duty",
  "sub": "Payable within 14 days of exercising the OTP",
  "narration": "Buyer's stamp duty is due within fourteen days..."
}
```

Duration and accent are filled in automatically: 4s hook, 10s per point, 6s CTA,
accents rotating in order. Override either by adding the key.

## Two known constraints

The container resets between chats, so re-clone each session. Claude cannot push
commits, so any engine improvement made during a session must be handed back and
committed by you or it is lost.
