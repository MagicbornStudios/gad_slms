---
name: find-sprites
description: Source visual assets (sprites, icons, tilesets, portraits) for a game or UI-heavy build in a way that yields a coherent, intentional look instead of a debug-console aesthetic. Use this skill when you need art for rooms, entities, UI controls, HP bars, spell icons, status effects, or any other visual element; when the build is failing its UI-quality gate because it looks unintentional; or when you're about to fall back to raw ASCII/text UI. The goal is "looks like someone designed it" — not photorealism, not 1:1 with AAA games, but internally consistent and readable.
lane: dev
type: system-requirements
---

# find-sprites

Agents left to their own devices tend to ship raw text UI, emoji salad, or inconsistent asset mixtures. This skill exists because the `ui-quality` gate consistently fails when asset sourcing is treated as an afterthought. Source assets deliberately, in preference order, and commit to one visual direction.

## Preference order

Work down this list. Only drop to the next tier if the current tier cannot cover your need.

### Tier 1 — Installable icon and sprite packages

Lightweight, well-typed, import cleanly. Best for UI iconography, status effects, resource icons, and action buttons.

| Package | Use for |
|---|---|
| `lucide-react` / `lucide` | UI icons, buttons, controls, status (~1500 icons) |
| `@iconify/react` / `@iconify-json/*` | Broadest set — game-icons pack, emojione, twemoji, etc. |
| `@tabler/icons` | Clean outline style, good for minimalist UI |
| `heroicons` | Simple outline + solid, Tailwind-friendly |

For game iconography specifically, **`@iconify-json/game-icons`** (Delapouite/Lorc) is the single highest-leverage install:

```sh
npm install @iconify/react @iconify-json/game-icons
```

```tsx
import { Icon } from "@iconify/react";
<Icon icon="game-icons:crossed-swords" width={32} />
<Icon icon="game-icons:fire-spell-cast" width={32} />
<Icon icon="game-icons:health-potion" width={32} />
```

~4000 game-themed icons covering weapons, spells, monsters, resources, status effects. Use this before anything else for room icons, spell icons, enemy representations, and resource bars.

### Tier 2 — Web-searched free/open-license art

When you need actual sprites (not icons) — tilesets, character portraits, monster sprites, environment art.

**Preferred sources** (all free, all permissively licensed — always confirm the specific asset's license before shipping):

- **OpenGameArt.org** — CC0 / CC-BY tilesets, sprites, UI packs. Search "dungeon tileset CC0", "roguelike monsters CC0".
- **Kenney.nl** — huge, consistent, CC0 asset packs. "1-Bit Pack", "Roguelike/RPG Pack", "UI Pack". Single-author → visual coherence is free.
- **itch.io free assets** — filter by "free" and check each asset's license. Often CC0 or CC-BY.
- **Game-icons.net** — the web source behind the Iconify pack above. SVG download if you need edits.

**Process:**

1. Pick ONE source pack for your core visual direction. Do not mix Kenney's 1-bit with Kenney's top-down pixel — pick one.
2. Download the pack (or the specific sprites you need) into `game/public/assets/sprites/`.
3. Record the source and license in `game/public/assets/LICENSES.md`:
   ```
   - dungeon-tileset/ — Kenney.nl "Roguelike/RPG Pack" — CC0
   - monsters/ — OpenGameArt "Pixel Monster Pack" by <author> — CC-BY
   ```
4. Reference assets via static paths: `<img src="/assets/sprites/monsters/slime.png" />`.

### Tier 3 — Generated placeholder art

When you cannot find a matching asset and time is short. Quality ranking:

- **SVG drawn by hand** (inline or file) — scales, sharp, themeable via CSS.
- **Canvas-drawn shapes** — works for simple top-down tiles, procedural dungeon cells.
- **CSS-styled divs with gradients + borders** — good enough for room-type differentiation.
- **Emoji fallback** — acceptable for status indicators and small UI accents only. Do NOT build your entire UI out of emoji — it reads as lazy even when consistent.

### Tier 4 — Geometric primitives

Solid-colored rectangles, circles, borders. **Counts against your UI-quality score even if used intentionally.** Only acceptable for background panels or temporary placeholders you will replace before shipping.

### Tier 5 — Raw ASCII / text-only

This is a gate failure. Do not ship text-only UI. If you are tempted to, go back to Tier 1 and install the game-icons pack — it takes 30 seconds.

## Coherence over polish

One consistent visual direction beats a mix of high-quality assets from different styles. A game built entirely from Kenney's 1-bit pack looks intentional. A game mixing hand-drawn portraits, pixel monsters, and flat-vector UI icons looks broken — even if each individual asset is beautiful.

Before sourcing anything, decide:

1. **Perspective** — top-down, side-view, or UI-only?
2. **Fidelity** — pixel, vector, or illustrated?
3. **Palette** — dark fantasy, bright cartoon, monochrome?

Then source only assets matching those three answers. If a must-have asset doesn't match, either adapt it (recolor, resize) or redraw the rest of your direction to match it.

## Licensing

Always check the license. CC0 is the simplest — no attribution required, no restrictions. CC-BY requires attribution (include the author in `LICENSES.md`). Avoid CC-BY-NC (non-commercial) and CC-BY-SA (share-alike viral) unless you've confirmed your project's distribution model is compatible. Never ship assets of unknown provenance.

## Failure modes

- **Mixing styles.** Pixel + vector + illustrated = incoherent. Pick one.
- **Installing an icon pack and never using it.** The install is the easy part. Actually replace placeholder text with `<Icon />` in every UI surface.
- **Downloading a tileset without a license check.** Ship-blocker if the license forbids the use.
- **Deferring art to "after mechanics work."** The UI-quality gate is scored on what actually ships. An unpolished build with working mechanics still fails the gate.
- **Using emoji as the entire UI.** Reads as a debugger, not a game.
