# Co-Work UI audit

This pass uses the local checkout at `vendor/avoid-ai-design/` (commit from the
`main` branch) as the audit reference. The app is treated as a `dashboard` and
the rewrite direction is **Swiss / International typographic**. The production
Streamlit UI and six-scene HTML prototype are both in scope.

## Findings before the rewrite

| Severity | Location | Finding | Confidence |
| --- | --- | --- | --- |
| P0 | `docs/frontend/prototype/style.css` and `src/frontend/theme.py` | A single neutral/system sans was used as the only typographic decision. | Code-certain in the original source |
| P0 | `docs/frontend/prototype/app.js` / `.welcome` | The prototype used a centered slogan hero with four identical suggestion cards. | Code-certain in the original source; confirmed by original PNGs |
| P1 | `docs/frontend/prototype/style.css` | Rounded cards, a soft composer shadow, and repeated surface treatment flattened hierarchy. | Code-certain in the original source; confirmed by original PNGs |
| P1 | `docs/frontend/prototype/app.js` | Raw arrow and decorative glyphs were attached to navigation and CTA labels. | Code-certain in the original source |
| P1 | `docs/frontend/prototype/app.js` | Prototype headings used vague promises such as “从一个好问题开始” and “一切状态，清晰可见”. | Code-certain in the original source |
| P2 | `src/frontend/pages/*` and prototype | Repeated captions and evenly distributed spacing weakened the information hierarchy. | Code-certain / render-confirmed for the original prototype |

## Committed direction

- **Type:** Avenir Next / Helvetica Neue for display text, PingFang / Hiragino for Chinese body text; weight and size carry the hierarchy.
- **Palette:** white and graphite as the dominant field; Apple blue is reserved for focus, links, and active state.
- **Layout:** flush-left content, narrow working measure, and rules instead of repeated cards.
- **Motion:** short functional transitions only; no decorative entrances or glow.
- **Signature detail:** a thin rule and compact text links for empty-state suggestions.

## Rewrite and re-audit

The theme now uses a deliberate display/body pairing, smaller radii, visible
focus states, and a quieter sidebar with hairline separators. The workbench
empty state is left aligned and concrete. The HTML prototype uses the same
tokens, removes decorative glyphs, and presents status and library content as
rows and tables. Existing conversation, upload, citation, inspector, and error
flows were preserved.

No P0 patterns from the catalog remain in the edited frontend source: there is
no gradient, glass surface, centered marketing hero, icon card grid, or emoji
navigation. The result is intentionally restrained for a research dashboard;
the grid and status colors carry the visual identity instead of decoration.

The checked-in PNGs are earlier prototype renders. Regenerating them requires
the optional Playwright/Chrome renderer; the current sandbox does not have that
dependency, so those images are not treated as current source behavior.
