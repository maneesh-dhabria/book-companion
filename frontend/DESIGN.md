# Book Companion — Design System

Bootstrapped: 2026-05-02 (from `frontend/src/assets/theme.css` + `docs/wireframes/2026-05-02-audiobook-mode/assets/house-style.css`).

```yaml
x-source:
  applied: true
  origin: frontend/src/assets/theme.css
  bootstrapped_by: /prototype (delegated to /wireframes targeted bootstrap)
```

## Identity

Book Companion is a single-user, local-first non-fiction summarization tool. Visual identity reads as a serious reading utility — calm light surfaces with a dark sidebar, indigo accent for action, generous typography, no decorative chrome.

## Tokens

### Color (light theme is canonical for wireframes & prototypes)

```yaml
color:
  bg:
    primary:   "#ffffff"
    secondary: "#f8f9fa"
    tertiary:  "#f1f3f5"
    elevated:  "#ffffff"
  text:
    primary:   "#1a1a2e"
    secondary: "#6b7280"
    muted:     "#9ca3af"
    accent:    "#4f46e5"
  border:
    default:   "#e5e7eb"
    strong:    "#d1d5db"
  accent:
    base:      "#4f46e5"   # indigo-600
    hover:     "#4338ca"
  status:
    success:   "#16a34a"
    warning:   "#d97706"
    error:     "#dc2626"
  sidebar:
    bg:        "#1e1e2e"
    text:      "#cdd6f4"
    active:    "#4f46e5"
  highlight:
    saved:     "#fef9c3"   # annotations, distinct from ::selection
```

Alternate themes — `dark`, `sepia`, `night`, `paper`, `contrast` — exist in `theme.css` but are reader-content scoped. Wireframes/prototypes target light only.

### Typography

```yaml
font:
  sans: "Inter, ui-sans-serif, system-ui, -apple-system, 'Segoe UI', Roboto, 'Helvetica Neue', sans-serif"
  mono: "ui-monospace, 'SF Mono', Menlo, Consolas, monospace"
size:
  xs:   "11px"   # chips, badges
  sm:   "13px"   # body-secondary, dense tables
  base: "14px"   # body
  md:   "16px"   # comfortable reading
  lg:   "20px"   # section heads
  xl:   "28px"   # page titles
weight:
  regular: 400
  medium:  500
  semibold: 600
```

### Shape

```yaml
radius:
  default: "8px"
  large:   "14px"   # playbar, cards
  pill:    "999px"  # chips, badges, coverage bars
shadow:
  default: "0 1px 2px rgba(0,0,0,.04), 0 4px 12px rgba(0,0,0,.04)"
  raised:  "0 -2px 12px rgba(0,0,0,.06)"  # playbar (sticky bottom)
spacing-base: "4px"   # all spacing is multiples of 4
```

## Layout

App shell on desktop is a fixed left **dark sidebar** (`240px`, `#1e1e2e`) + flexible main content. Sidebar holds library nav, search, settings link. Mobile collapses sidebar behind a hamburger; bottom tab bar replaces it.

```yaml
x-information-architecture:
  shell:
    desktop: "fixed-left-sidebar + main"
    mobile:  "top-bar + main + bottom-tab-bar"
  layouts:
    library-list:
      skeleton: "sidebar | (top-bar) (book-grid)"
      use_for:  "browsing books, search results"
    book-detail:
      skeleton: "sidebar | (top-bar) (book-header) (tab-strip) (tab-content)"
      use_for:  "single-book pages: Overview / Summary / Sections / Audio / Annotations"
    reader:
      skeleton: "sidebar | (reader-header) (reading-area) (footer-nav) [+ floating-toolbar | sticky-playbar]"
      use_for:  "reading any section with optional audio playbar"
    settings:
      skeleton: "sidebar | (settings-nav) (settings-pane)"
      use_for:  "all preference panes"
```

## Components (prose; canonical inventory in COMPONENTS.md)

- **Buttons**: rectangular, `8px` radius. Primary = filled indigo; secondary = white surface + border; ghost = text-only with hover bg. Destructive = red border + red text on white, fills red on hover. Min height 36px desktop, 44px mobile.
- **Inputs**: white surface, `8px` radius, `1px solid #d1d5db` border. Focus = `2px` indigo outline (`box-shadow: 0 0 0 2px rgba(79,70,229,.4)`).
- **Cards**: white surface, `14px` radius, default shadow. Padding `16–24px`.
- **Modals**: centered, white surface, `14px` radius, `0 20px 50px rgba(0,0,0,.18)` shadow, `560px` typical width. Backdrop `rgba(0,0,0,.45)`.
- **Toasts**: bottom-right on desktop, top-center on mobile. Auto-dismiss 4s. Success/warning/error variants.
- **Chips/Badges**: `999px` pill, `11–13px` text. `bc-engine-chip` for TTS engine indicator (Kokoro = filled indigo tint; Web Speech = neutral grey).
- **Coverage bar**: `6px` thin progress bar, pill-rounded, neutral track + indigo fill.
- **Playbar (sticky bottom)**: `bc-playbar` — white, `14px` radius, raised shadow. Holds play/pause, sentence skip, speed control, engine chip, sentence index.
- **Sentence highlight**: `bc-sentence-active` — accent-tinted underline-style background on the currently-spoken sentence.
- **Banners**: `bc-banner` — warning (amber tint) and info (indigo tint) variants. Inline within page flow, not floating.

## x-interaction

```yaml
x-interaction:
  modals:
    style: centered
    dismiss: [backdrop-click, esc-key, explicit-button]
  destructiveActions:
    confirmation: type-to-confirm   # used for "Delete audio for this book"
  focus:
    trapInModals: true
    visibleStyle: "outline: 2px solid #4f46e5; outline-offset: 2px;"
  defaultStates:
    empty: minimal     # icon + one-line message + CTA, no illustration
    loading: skeleton  # skeleton blocks for cards/tables; spinner only for inline
    error: inline-banner
  shortcuts:
    "Space":     "play/pause active audio"
    "ArrowLeft":  "previous sentence"
    "ArrowRight": "next sentence"
    "?":         "open keyboard shortcut help"
    "/":         "focus search"
    "Esc":       "close modal / dismiss banner"
  audio:
    autoAdvance: true        # section → next section by default (settable)
    rememberPosition: true   # per-browser, server-persisted
```

## x-content

```yaml
x-content:
  voice:
    tone: "calm, factual, second-person where action-oriented"
    avoid: ["exclamation marks", "marketing hype", "emoji in copy"]
  buttonVerbs:
    primary:    "Save"      # not "Submit"
    create:     "Create"    # not "Add"
    destroy:    "Delete"    # not "Remove"
    listen:     "Listen"
    generate:   "Generate"
    regenerate: "Regenerate"
  formats:
    date:     "MMM D, YYYY"        # "May 2, 2026"
    dateTime: "MMM D, YYYY · h:mma" # "May 2, 2026 · 2:14pm"
    duration: "M:SS / M:SS"        # "2:14 / 6:08"
    fileSize: "iec-binary"          # "140 MB" not "140000000 bytes"
    sentenceIndex: "sentence N of M"
```

## Anti-patterns

- **Do not** introduce a second accent color. Indigo `#4f46e5` is the only action color. **Specifically**: status pills (e.g., "running", "ready") and info banners must NOT use a separate blue palette like `#1e40af` / `#dbeafe`. Use the indigo ramp (`#eef2ff` bg, `#c7d2fe` border, `#3730a3` text) for indigo-tinted variants, or the neutral grey ramp for purely informational chrome. This avoids tonal collision with the EngineChip and keeps "engine" / "status" / "info" visually disambiguated.
- **Do not** use illustrations or stock imagery for empty states. Single icon + sentence + CTA.
- **Do not** put destructive actions inline in dropdown menus without confirmation.
- **Do not** use slide-up drawers on desktop — modals are centered.
- **Do not** use Lorem ipsum or "User 1 / Book 2" placeholder data. Use domain-real titles (real public-domain books, real summary phrasing).
- **Do not** spell out file sizes in bytes or use locale-formatted commas in technical contexts.
- **Do not** auto-pause audio on tab switch — that contradicts the "walk away from the screen" job.
- **Do not** mix engine chips and book-status chips visually — engine chip uses indigo tint; book-status uses neutral surfaces.

## Do's and Don'ts

- **Do** show engine + voice name on the playbar at all times — users compare engines mid-session.
- **Do** show inline cost estimates on generate-audio CTAs ("~12 min · ~140 MB for 47 sections").
- **Do** show resume context as "from this browser" not "from this device".
- **Do** keep buttons rectangular (8px radius) and chips pill-rounded; don't blend the shapes.
- **Do** use the dark sidebar as visual ground — the main content is the figure.
- **Don't** wrap card grids in dashboards — Book Companion is a reader, not a dashboard.
