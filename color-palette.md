# Corsair — Color Palette

## Backgrounds

| Token | Hex | Usage |
|---|---|---|
| `deep` | `#020B18` | Page background |
| `abyss` | `#05152A` | Panels, modals, cards |
| `navy` | `#0A2444` | Elevated cards, topbar |
| `ocean` | `#0D3366` | Hover states |
| `horizon` | `#0F4C8A` | Card borders, dividers |

## Brand Blues

| Token | Hex | Usage |
|---|---|---|
| `wave` | `#1A6FB5` | Primary buttons, brand gradient |
| `sky` | `#2B9ED4` | Links, interactive elements |
| `foam` | `#5EC4F0` | Labels, captions, accent text |
| `mist` | `#A8DCF2` | Secondary / muted text |
| `white` | `#EEF6FF` | Primary text |

## Semantic

| Token | Hex | Usage |
|---|---|---|
| `teal` | `#00D4B4` | Success, done, accent dot |
| `gold` | `#F0A500` | Warning, running, in-progress |
| `coral` | `#E8445A` | Error, failed |

## Gradients

| Name | Value | Usage |
|---|---|---|
| Brand | `linear-gradient(135deg, #1A6FB5, #0F4C8A)` | Buttons, logo bg, CTAs |
| Sail | `linear-gradient(135deg, #5EC4F0, #1A6FB5 70%)` | Logo main sail |
| Fore sail | `linear-gradient(135deg, #A8DCF2 70%, #2B9ED4)` | Logo fore sail |

## Tailwind Config

```ts
// tailwind.config.ts
colors: {
  deep:    '#020B18',
  abyss:   '#05152A',
  navy:    '#0A2444',
  ocean:   '#0D3366',
  horizon: '#0F4C8A',
  wave:    '#1A6FB5',
  sky:     '#2B9ED4',
  foam:    '#5EC4F0',
  mist:    '#A8DCF2',
  white:   '#EEF6FF',
  teal:    '#00D4B4',
  gold:    '#F0A500',
  coral:   '#E8445A',
}
```

## Rules

- **Dark mode only** — no light mode
- Background is always `deep`, never pure black
- Cards use `abyss` + `1px` border at `foam` with `8%` opacity
- Primary buttons use the Brand gradient
- Status: `teal` = done · `gold` = running · `coral` = failed · `foam` = backlog
- Fonts: **Inter** for UI · **JetBrains Mono** for logs and code