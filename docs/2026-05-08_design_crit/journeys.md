# Journeys (user-specified, no inference)

Entry context for all three: signed-in single user (local tool), warm — book exists, summaries exist.

## J1 — Library → Book Summary

1. Land on `/` (Library page)
2. Click book card "Understanding Michael Porter"
3. Land on `/books/1` (BookSummaryPage)
4. Inspect: hero, summary content, section list, action affordances

## J2 — Book → Section Detail

1. From `/books/1`, click a section in the section list (or navigate directly)
2. Land on `/books/1/sections/3` (Introduction)
3. Inspect: section header, content/summary toggle, navigation, reading affordances

## J3 — Audio playback

1. From either `/books/1` or `/books/1/sections/3`, locate the "Listen" button
2. Click — audio player initiates
3. Inspect: player chrome, loading/buffering state, controls, position persistence, seek/scrub, close
