---
title: Design decisions
updated: 2026-10-24
---

# Design decisions

[← Index](README.md)

Why the site looks and behaves as it does. Each decision lists what was chosen, why, and the
source behind it, so a future change can tell a rule from a preference.

## Calm dark theme, no navy

- **Chosen:** one dark surface (page `#181818`, cards `#222222`), text `#e6e6e6` instead of pure white,
  no blue-tinted or navy colours anywhere, no scanline texture.
- **Why:** the owner asked for no navy. Off-white on dark grey instead of white on black reduces
  glare ("halation") during long reading.
- **Source:** Material Design dark theme guidance, <https://m3.material.io/styles/color/dark-theme>.
- **Note:** this departs from the dashboard's Mythological Punk theme (navy, cobalt, brass). The
  dashboard itself is unchanged.

## Brand colour as an accent, not a fill

- **Chosen:** each provider's colour appears only on its section heading, the strip along each card,
  the tag outline, and the compare table's column top.
- **Why:** full-width orange, white and black bands (tried first) made the eye re-adapt at every
  section and were tiring. One shared card style also lets models be compared on equal terms.
- **Colours:**

| Provider | Accent | Source |
| --- | --- | --- |
| Anthropic | orange `#d97757` | Anthropic brand guidelines (dark `#141413`, light `#faf9f5`, orange `#d97757`) |
| OpenAI | light grey `#e6e6e6` | OpenAI brand guidelines (2022) say its primary palette is black and white and "OpenAI has no singular brand color" |
| Ollama | light grey `#e6e6e6` | Ollama's site uses black and white (third-party token extraction, designmd.co) |
| Nous | neutral grey outline | Nous's brand booklet calls its palette "the blues of Nous", but the exact shade was not confirmed, so no blue is guessed |

OpenAI and Ollama share an accent because both brands are black and white; they are told apart by
section name, tag and order.

## Accessibility

Measured against WCAG 2.2 (<https://www.w3.org/TR/WCAG22/>):

- **1.4.3 Contrast (minimum):** body text needs 4.5:1. Lowest on the site is Anthropic orange at
  5.1:1; main text is 12.7:1 on cards.
- **1.4.1 Use of colour:** never colour alone. Links are underlined; selected cards say
  "✓ Comparing"; every section and tag carries the provider's name.
- **1.4.11 Non-text contrast:** cards have a faint outline so their edges show.
- **Motion:** transitions are switched off for viewers who ask for reduced motion.
- **Phone width:** no sideways scrolling at 390 px; the compare table scrolls inside its own box
  with row labels pinned.

## Minimal content

The first version carried pipeline explanations, rules and run commands. The owner asked for a
minimal approach, so the site now holds only the feed and the catalog. Those explanations live in
this knowledge base instead.

## Feed matches the dashboard exactly

The feed tab reuses the dashboard's display rules (filters, stale banner, "first seen", "new"
badge) and `build.py` reuses its data checks, so the two never disagree about what a story is.

Related: [The site](site.md).
