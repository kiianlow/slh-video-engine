# Spec conflicts resolved

The docs in this folder were written at different times and disagree with each
other in seven places. Every one of them was a decision you were re-making by
hand each session. They are now settled in `config/brand.json`, which is the
only thing the engine reads.

| # | Conflict | Sources | Resolved to | Why |
|---|---|---|---|---|
| 1 | **Font** | `brand-guidelines.md` says Nunito Sans. `SLH_Motion_Graphics_Workflow.md` says Poppins, locked, do not substitute. | **Nunito Sans** | Poppins only ever won because Nunito Sans was not installed in the render environment. Both weights are now cut from the official variable font and committed to `assets/fonts/`. The reason for the substitution is gone, so the substitution is gone. |
| 2 | **Frame rate** | Workflow doc says 30fps. Later spec says 60fps locked. | **60fps**, with `draft_fps: 30` | 60 is the platform ceiling and the later decision. 30 stays available via `--draft` for quick checks, since it halves an 11 minute render to 5.6. |
| 3 | **Voice** | Workflow doc says Adam, 67/75/0. Later spec says George, 55/80/5, boost on. | **George** | Later decision supersedes. Adam settings kept in this table only. |
| 4 | **Background audio** | Workflow doc says lo-fi from Pixabay. Caption patch says "minimal modern underscore (NOT lo-fi)". | **Your actual file**, `Lofi_BG_music.mp3` at gain 0.10 | You supplied the track you actually use. A doc arguing against lo-fi loses to the lo-fi file you have been using. |
| 5 | **Icon source** | Three different answers: Streamline SVG pack, Flaticon PNG library, Fluent UI Emoji. | **Flaticon PNG library**, Fluent-style, indexed in `config/icons.json` | The 22-icon index is the most recent and most specific. Fluent UI Emoji is the *style* target, not a second library. Never mix two icon styles in one project. |
| 6 | **Captions** | Workflow doc renders silent and adds captions in CapCut. Caption patch v2.1 burns them in word by word. | **Burned in**, word by word | v2.1 is the later spec and removes a manual step. `captions.py` does it. |
| 7 | **Palette** | Video uses `#E8E0D0` / `#3D2B1F`. Thumbnail uses `#F5E5D3` / `#4E3321` / `#B87A4C`. | **Both kept**, under `palette.video` and `palette.thumbnail` | Not resolved, deliberately. See below. |

---

## The one thing left for you to decide

The thumbnail and the video are on slightly different beiges and browns. The
thumbnail runs warmer and lighter.

Side by side in a feed this reads as two related but not identical assets. That
may be intentional, since a thumbnail competes at grid scale and a warmer, higher
contrast version pops harder. It may also just be drift from building them at
different times.

Both palettes are preserved in config so nothing changed under you. Say the word
and I will unify them in one edit, in either direction.

---

## Substitutions still active

**The 22 icon PNGs are not in the project files.** Only three font specimen
images and the logo were there. `config/icons.json` maps every scene key to the
correct filename from `SLH_icon_index.md`, so the moment you drop the pack into
`assets/icons/` with these folder names, every icon resolves to the real art
with no code change:

```
assets/icons/Property and buildings/*.png
assets/icons/money and finance/*.png
assets/icons/signs/*.png
```

Until then the engine generates a Fluent-style stand-in per icon, caches it, and
prints a flag at the end of every run. It never blocks a render. The six icons
flagged red in the index get recoloured into the scene accent automatically once
the real files are present.
