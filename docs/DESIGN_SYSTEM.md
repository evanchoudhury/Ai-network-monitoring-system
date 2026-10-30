# Sentinel AI — Design System

> **On Figma/Canva:** this environment did not expose an authenticated,
> verifiable Figma or Canva session, so **no Figma file or Canva design was
> created** (claiming otherwise would be dishonest). Instead, this document is
> an implementation-ready design specification, the brand assets are delivered
> as real hand-authored SVGs (see `docs/BRANDING.md` and `frontend/public/`),
> and the **working React app is the realized design system** — every token and
> component below exists in code under `frontend/src/`. The spec is structured
> so it can be reproduced in Figma 1:1 if desired.

## 1. Design tokens

### Color (exact values — defined in `frontend/tailwind.config.js`)
| Token | Hex | Usage |
|---|---|---|
| Background | `#050A12` | App background |
| Sidebar | `#091321` | Navigation rail |
| Card | `#0D1928` | Default surface |
| Elevated card | `#122238` | Raised surface, inputs, controls |
| Border | `#1D3349` | Hairline borders, dividers |
| Primary cyan | `#20D9F2` | Primary accent, normal nodes |
| Primary blue | `#338BFF` | Primary actions, high-traffic nodes |
| Teal | `#13D6C1` | Secondary accent, connection lines |
| Success green | `#20D99A` | Healthy / confirmed states |
| Warning amber | `#FFBF47` | Warnings, anomaly nodes |
| Critical red | `#FF5268` | Critical alerts, suspicious links/nodes |
| Primary text | `#ECF5FF` | Headings, values |
| Secondary text | `#8DA4BC` | Labels, muted copy |

### Typography
- **UI sans:** Inter (400/500/600/700).
- **Numeric / mono:** JetBrains Mono — used for metric values, scores, timestamps.
- **Scale:** Display 20px/600 · Section title 13px/600 uppercase tracking-wide ·
  Body 14px/400 · Caption 11–12px · KPI value 24px/600 mono.

### Spacing & radius
- Base unit 4px. Card padding 16px. Grid gaps 12–16px.
- Radius: cards 12px (`rounded-xl`), controls/chips 8px, pills full.

### Elevation & effects
- Card: 1px border `#1D3349` over surface fill; subtle shadow.
- Glow: cyan/blue box-shadow on active nav and map nodes (restrained).
- Motion: `fadeIn` on mount; `pulseGlow` on alert/anomaly nodes only; all motion
  disabled under `prefers-reduced-motion`.

## 2. Components (implemented in `frontend/src/components/`)

| # | Component | File | Notes |
|---|---|---|---|
| 1 | Sidebar navigation | `Layout.tsx` | 12 items, active glow, collapses < lg |
| 2 | Top navigation bar | `Layout.tsx` | breadcrumb, mode indicator, alert bell |
| 3 | KPI card | `KpiCard.tsx` | label, mono value, accent icon, sparkline |
| 4 | Traffic charts | `charts.tsx` | area/line, compact axes, themed tooltip |
| 5 | Global network map | `NetworkMap.tsx` | d3-geo, zoom/pan, arcs, particles, legend |
| 6 | Network nodes | `NetworkMap.tsx` | color = severity; glow; pulse on alert/anomaly |
| 7 | Security alert card | `shared.tsx` (`AlertRow`) | severity dot, category, source, ack |
| 8 | News card | `pages/News.tsx` | headline, publisher, topic, source link |
| 9 | Claim-verification card | `pages/Claims.tsx` | label, evidence split, limitations |
| 10 | Spam result | `pages/Spam.tsx` | category, indicators, link flags, action |
| 11 | System-health indicator | `pages/Health.tsx` | ok/degraded/down icons |
| 12 | Notifications | `Layout.tsx` | alert badge on bell |
| 13 | Search controls | inputs in pages | `.input` token |
| 14 | Filters | `pages/NetworkMapPage.tsx` | severity/layer checkboxes |
| 15 | Modal/overlay | mobile drawer in `Layout.tsx` | |
| 16 | Tables | `pages/Sources.tsx` | responsive, overflow-x |
| 17 | Empty states | `ui.tsx` (`EmptyState`) | icon + hint + action |
| 18 | Loading states | `ui.tsx` (`LoadingState`) | spinner |
| 19 | Error / unavailable states | `ui.tsx` (`ErrorState`) | distinguishes 0/503 |
| 20 | Mobile navigation | `Layout.tsx` | bottom nav + drawer |

## 3. Pages

Desktop pages (`frontend/src/pages/`): Overview, Global Network Map, Network
Traffic, Security Threats, News Intelligence, Claim Verification, Spam &amp;
Phishing, Reports, Data Sources, System Health, Budget &amp; Usage, Settings.

### Responsive behaviour
- **Desktop (≥1280px):** full sidebar, large map, multi-column KPI grid (5-up),
  side-by-side panels.
- **Tablet (≥768px):** collapsible sidebar (drawer), 2–3 column grids.
- **Mobile (<768px):** compact header with menu, 2-up KPI grid, full-width
  charts, bottom navigation, touch-friendly map, no horizontal page scroll.

## 4. Global network map — interaction spec

- **Node colors:** cyan = normal · blue = high traffic / monitored · amber =
  detected anomaly · red = high-severity alert.
- **Lines:** teal solid = ordinary observed connection · red dashed = suspicious
  (only when event-backed).
- **Interactions:** zoom (buttons + wheel), pan (drag), select node (details
  panel), reset view, pause/play animation, severity + layer filters, time-range
  filter. Animated particles respect `prefers-reduced-motion`.
- **Honesty:** only located, authorized nodes/connections are plotted; unlocated
  services are counted separately and never given invented coordinates; demo
  data carries a visible **DEMO DATA** tag.

## 5. Accessibility
- Color is never the sole signal (icons + text labels accompany severity colors).
- Focus-visible outlines on interactive controls; semantic headings.
- Reduced-motion fully supported. Touch targets ≥ 32px on mobile.
