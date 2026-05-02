# Audiobook Mode — Wireframe Brief (shared across all components)

Feature: Audiobook Mode for Book Companion. Two TTS engines (Web Speech instant-play, Kokoro local for pre-generated MP3s). Single-user self-hosted app.

## Hard rules every wireframe must follow

1. **Skeleton:** use the html-template skeleton from the wireframes skill (state-switcher tabs, annotations toggle, device frame, footer).
2. **CSS:** link `./assets/wireframe.css` THEN `./assets/house-style.css` (in that order). Tailwind via `<script src="https://cdn.tailwindcss.com"></script>`. Do NOT inline the rules from those stylesheets.
3. **Font:** Add `<link rel="preconnect" href="https://fonts.googleapis.com">` and load Inter via Google Fonts (`https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap`).
4. **Accent color** is indigo `#4f46e5` (already set in house-style.css as `--wf-accent`). Use `mock-button--primary` for primary CTAs.
5. **Use the vocabulary:** `mock-card`, `mock-button`, `mock-input`, `mock-pill`, `mock-divider`, `skeleton`, `wf-message`, plus the app-specific primitives: `bc-sidebar`, `bc-playbar`, `bc-sentence-active`, `bc-engine-chip` / `bc-engine-chip--web`, `bc-coverage-bar`, `bc-banner` / `bc-banner--info`.
6. **Realistic copy:** pull from real book titles. Use: "Thinking, Fast and Slow" by Daniel Kahneman, "The Coddling of the American Mind" by Haidt & Lukianoff, "Atomic Habits" by James Clear. Section names like "System 1 and System 2", "The Two Selves", "Cue, Craving, Response, Reward". Realistic dates ("2 hours ago", "May 2, 2026"). Realistic file sizes (3.2 MB, 1.8 MB).
7. **Engine labels:** ALWAYS show which engine is active (Web Speech vs Kokoro). Use `bc-engine-chip` for Kokoro-active, `bc-engine-chip--web` for Web Speech.
8. **Annotations:** wrap non-obvious interactions with `class="wf-anno" data-note="…"`. Examples worth annotating: auto-advance behavior, media-session lock-screen integration, atomic MP3 replace on regenerate, sentence-level highlight not word-level.
9. **Accessibility:** `aria-label` on icon-only buttons, focus-visible (already styled), 44×44px tap targets on mobile, `aria-live="polite"` regions for sentence highlight.
10. **Footer:** include component name, device chip, "File NN of 14", date "2026-05-02", and the back-to-index link to `./index.html`.

## App layout reference (so wireframes feel like Book Companion)

- **Reader page** = dark sidebar (`bc-sidebar`, ~240px) listing sections + book chrome on top (book title + author) + main content area (max-w-4xl, generous prose typography, `--color-bg-primary` white).
- **Book detail page** = page header (book cover thumbnail mock-img + title + author + status pills) + tabs row (Overview, Sections, Annotations, Concepts) + tab content area.
- **Settings page** = left side-nav of sections (LLM, Database, Presets, Reading, **TTS** — new), right pane with form sections.
- **Modals** = centered overlay, max-width 540px, `mock-card` body with header / content / button-row footer.

## Key product strings (use verbatim where natural)

- "Generate audio"
- "Listen"
- "Audio files"
- "Regenerate audio"
- "Delete audio for this book"
- "Play as audio" (annotations playlist entry)
- "Loading voice…" (cold-start indicator)
- "Resume from sentence 12 of 47 · last listened on this device 2 hours ago"
- "Web Speech (browser, instant)" / "Kokoro local (higher quality)"
- "Audio: 12 of 47 sections pre-generated"
- "Source has been edited since audio was generated. Regenerate?"
- "Summary updated since this audio was generated. Regenerate audio for the new summary?"
- "Audio is only generated for summaries in v1. Generate this section's summary first."

## Engine-fallback mental model (from D14 — IMPORTANT)

- **Click play in reader, no pre-gen MP3 exists** → instant Web Speech, regardless of default-engine setting.
- **Click play in reader, pre-gen MP3 exists** → Kokoro MP3 stream.
- **Generated audio (downloads)** → always Kokoro.
- The player header shows the active engine; the section list shows a small icon next to sections that have pre-gen audio.
