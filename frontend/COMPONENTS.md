# Book Companion — Component Inventory

Bootstrapped: 2026-05-02 (from `frontend/src/components/` directory walk).
Companion to `DESIGN.md`. Generators (wireframes, prototype) prefer existing variants from this list before inventing new ones.

## Atoms

| Name | File | Variants | Notes |
|---|---|---|---|
| Button | (Tailwind, no shared component) | `primary`, `secondary`, `ghost`, `destructive`, `icon-only` | Min height 36/44 desktop/mobile. Uses `x-content.buttonVerbs`. |
| Input | (Tailwind) | `text`, `search`, `password`, `with-affix` | Focus = 2px indigo outline. |
| TagChip | `common/TagChip.vue` | `default`, `removable` | Pill, neutral surface. |
| TagChipInput | `common/TagChipInput.vue` | `default` | Multi-tag input with removable chips. |
| ContrastBadge | `common/ContrastBadge.vue` | `accent`, `success`, `warning`, `error`, `muted` | Pill, semantic color. |
| CoverFallback | `common/CoverFallback.vue` | `book-cover` | Generated-from-title gradient when no cover image. |
| LoadingSpinner | `common/LoadingSpinner.vue` | `inline`, `centered` | For inline waits; skeletons preferred for blocks. |
| SkeletonLoader | `common/SkeletonLoader.vue` | `text`, `card`, `table-row`, `cover` | Default loading-state primitive. |
| EngineChip | (new for audiobook) | `kokoro`, `web-speech` | Pill; kokoro = indigo tint; web-speech = neutral. |
| CoverageBar | (new for audiobook) | `default` | 6px pill progress bar. |

## Composites

| Name | File | Variants | Notes |
|---|---|---|---|
| EmptyState | `common/EmptyState.vue` | `default` | Icon + title + body + CTA. Minimal — no illustration. |
| ErrorBoundary | `common/ErrorBoundary.vue` | `inline-banner` | Default error rendering. |
| ConfirmDialog | `common/ConfirmDialog.vue` | `default`, `destructive` | Centered modal. Destructive = type-to-confirm. |
| BottomSheet | `common/BottomSheet.vue` | `default` | Mobile-only — desktop uses centered modal. |
| PresetGrid | `common/PresetGrid.vue` | `default` | Grid of selectable preset cards. |
| PresetPickerModal | `common/PresetPickerModal.vue` | `default` | Centered modal containing PresetGrid. |
| PresetsFetchError | `common/PresetsFetchError.vue` | `inline-banner` | Specialized error state. |
| ToastContainer | `common/ToastContainer.vue` | `success`, `warning`, `error` | Bottom-right desktop / top-center mobile, auto-dismiss 4s. |
| ThemeCard | `shared/ThemeCard.vue` | `selectable` | Used in settings → theme picker. |

## Layout / Shell

| Name | File | Variants | Notes |
|---|---|---|---|
| AppShell | `app/AppShell.vue` | `default` | Sidebar + main wrapper; routes the layouts in DESIGN.md `x-information-architecture`. |
| TopBar | `app/TopBar.vue` | `default` | Search + breadcrumbs + user menu. |
| IconRail | `app/IconRail.vue` | `default` | Narrow icon column (collapsed sidebar variant). |
| BottomTabBar | `app/BottomTabBar.vue` | `mobile` | Mobile-only nav. |
| ProcessingBar | `app/ProcessingBar.vue` | `default` | Sticky job-progress strip; reused for audio-generation jobs. |

## Reader-specific

| Name | File | Variants | Notes |
|---|---|---|---|
| ReaderHeader | `reader/ReaderHeader.vue` | `default` | Section title + breadcrumb + content toggle. **Audio play button slots in here.** |
| ReadingArea | `reader/ReadingArea.vue` | `default` | Markdown content surface; sentence highlight applies here via `bc-sentence-active`. |
| ReadingAreaFooterNav | `reader/ReadingAreaFooterNav.vue` | `default` | Prev/next-section nav. |
| MarkdownRenderer | `reader/MarkdownRenderer.vue` | `default` | Sanitized markdown → HTML. **Sentence-wrap pass for TTS happens here.** |
| ContentToggle | `reader/ContentToggle.vue` | `summary-vs-original` | Tab switcher; audio plays from the active tab. |
| FloatingToolbar | `reader/FloatingToolbar.vue` | `selection`, `audio-overlay` | Selection-anchored. Possibly extended for audio scrub. |
| ContinueBanner | `reader/ContinueBanner.vue` | `default` | "Resume from sentence X of Y…" — direct reuse for audio resume. |
| TOCDropdown | `reader/TOCDropdown.vue` | `default` | Section list dropdown; gains audio-status icons in the audiobook feature. |
| EvalBadge | `reader/EvalBadge.vue` | `pass`, `partial`, `fail` | Quality indicator. |
| SummaryEmptyState | `reader/SummaryEmptyState.vue` | `default` | Specialized EmptyState for "no summary yet". |
| SummaryFailureBanner | `reader/SummaryFailureBanner.vue` | `default` | Specialized ErrorBoundary. |
| SectionTagRow | `reader/SectionTagRow.vue` | `default` | Tags inline in section header. |
| Playbar | (new for audiobook) | `default`, `compact` | Sticky bottom; uses `bc-playbar` shape. |

## Components proposed by `/prototype` for audiobook-mode

These are NEW and must be flagged in the prototype's footer for /verify confirmation:

- **EngineChip** (atom) — engine + voice name pill, two variants.
- **CoverageBar** (atom) — book-level audio coverage indicator.
- **Playbar** (composite) — sticky-bottom audio control surface.
- **GenerateAudioModal** (composite) — content/voice/cost-estimate confirmation modal.
- **AnnotationPlaylistRow** (composite) — annotation card with attached play state + cue divider.

## Conventions

- File naming: `PascalCase.vue` per Vue conventions.
- Tailwind utility-first; tokens read from `theme.css` via CSS variables.
- No external icon library — Heroicons inlined as SVG (per existing usage).
- Components in `__tests__/` are Vitest unit tests, not part of the inventory.
