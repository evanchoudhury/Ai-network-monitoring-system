# Sentinel AI — Branding

> **On Canva:** no authenticated Canva session was available/verifiable in this
> environment, so **no Canva design was created**. The brand assets below are
> real, hand-authored SVGs (and PNG rasterizations) committed to this repo, plus
> a precise brief so they can be recreated or extended in Canva/Figma if desired.

## Brand direction

A cybersecurity **shield** fused with a **connected-network** motif (nodes +
links), rendered in the product's cyan/teal palette on deep navy. Minimal,
technical, and legible down to a 16px favicon. Not derived from any existing
company's mark.

## Delivered assets

| Asset | File | Format | Size |
|---|---|---|---|
| App icon / favicon | `frontend/public/favicon.svg` | SVG | 512 (scalable) |
| Maskable icon | `frontend/public/favicon-maskable.svg` | SVG | 512 |
| PWA icon 192 | `frontend/public/icon-192.png` | PNG | 192×192 |
| PWA icon 512 | `frontend/public/icon-512.png` | PNG | 512×512 |
| PWA maskable 512 | `frontend/public/icon-512-maskable.png` | PNG | 512×512 |
| Apple touch icon | `frontend/public/apple-touch-icon.png` | PNG | 180×180 |
| Horizontal logo lockup | `design/brand/logo-horizontal.svg` / `.png` | SVG/PNG | 520×120 |
| Icon (standalone) | `design/brand/icon.svg` | SVG | 512 |
| Social / repo preview | `design/brand/social-preview.svg` / `.png` | SVG/PNG | 1280×640 |

The PWA PNGs were produced by rasterizing the SVGs with headless Chromium, so
they match the vector source exactly.

## Color & type

- Palette: see `docs/DESIGN_SYSTEM.md` §1 (cyan `#20D9F2`, blue `#338BFF`, teal
  `#13D6C1` on navy `#050A12`).
- Typeface: **Inter** for the wordmark (700 weight, letter-spaced); subtitle in
  Inter 500 with wide tracking.

## Logo construction

- **Mark:** a shield outline stroked with a cyan→blue gradient; inside, four
  network nodes (one cyan apex, two blue flanks, one teal base) joined by teal
  links.
- **Clear space:** keep padding ≥ 25% of the mark height around the lockup.
- **Minimum size:** mark legible at 24px; wordmark lockup at ≥ 120px wide.
- **Do not:** recolor outside the palette, add drop shadows beyond the subtle
  glow, stretch, or place on low-contrast backgrounds.

## Usage

- **GitHub social preview:** upload `design/brand/social-preview.png`
  (Settings → Social preview).
- **Favicon / PWA:** already wired via `index.html` and the PWA manifest in
  `frontend/vite.config.ts`.
- **README header:** uses `frontend/public/favicon.svg`.

## Recreating in Canva/Figma (brief)

1. Canvas: navy `#050A12`. Add a rounded-square tile `#0A1627`.
2. Draw the shield path; apply a linear gradient `#20D9F2 → #338BFF`, stroke
   ~16px, round joins, no fill.
3. Place four circles (apex cyan, two blue, base teal) and connect with thin
   teal lines; add a soft outer glow.
4. Wordmark: "SENTINEL AI" in Inter Bold, letter-spacing ~2; color the "AI"
   cyan. Subtitle "NETWORK & TRUTH INTELLIGENCE" in Inter Medium, muted
   `#8DA4BC`, wide tracking.
5. Export icon at 192/512 PNG and the lockup/social banner as needed.
