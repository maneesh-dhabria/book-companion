# Grill Report — `01_requirements.md` (quiz-audio-ux-top7)

**Date:** 2026-05-10
**Depth:** standard
**Questions asked:** 8
**Outcome:** 8 resolved (1 codebase, 7 user-confirmed), 7 doc gaps to apply, 4 OQs deferred to /spec or wireframes

---

## Resolved

| # | Branch | Disposition |
|---|--------|-------------|
| 1 | Q-3 backend root cause | Diagnose now, add a `## Backend Defect` subsection to requirements before `/spec`. /spec opens with a known target, not a black-box repro. |
| 2 | OQ-3 / D3 listen-time formula | Pre-gen `word_count ÷ wpm` where `wpm = 200` is an env constant exposed in Settings → TTS for user override. |
| 3 | G2 cold-start measurability | Pre-warm voices on `AudioTab.vue` mount (`speechSynthesis.getVoices()` + await `voiceschanged`). Makes ≤2s first / ≤1s subsequent achievable on cold E2E runs. |
| 4 | D1 toast lifecycle | Sticky for actionable (Retry-bearing); 4s auto-dismiss for confirmations; dedupe by message within a 5s window; clear on retry success. |
| 5 | D2 populated audio state (gap not in original doc) | Listen CTA persists alongside Generate after MP3s exist. New requirement: engine picker drives Listen between Web Speech and queued MP3s. Empty-state copy adapts to "X of Y sections have MP3s". |
| 6 | D3 partial-state estimate | Delta for X (gen time) and Z (disk); total for Y (listening duration, since playback covers the whole book). |
| 7 | OQ-5 / D1 toast vs inline retry | Toast carries the actionable Retry; inline region under Start is diagnostic-only (failure reason + Dismiss). No double-Retry. |
| 8 | OQ-6 / D6 reversal (resolved from code) | `SpikeFindingsBlock.vue` carries the user-valuable "Listen to comparison" A/B button — D6 flips from "remove entirely" to "rename heading to 'Compare voices' + clean dev-only fallback". Heading → "Compare voices"; dev fallback hidden from end users; comparison button preserved. Update G6 measurement: assert no `Spike` string AND comparison button still present. |

## Open / Deferred (no change needed in requirements)

- OQ-1 — Quiz orientation copy wording (resolve in /spec or wireframes).
- OQ-2 — Audio CTA labels exact text (resolve in wireframes).
- OQ-4 — Backend-fixed quiz question count (resolve in /spec from backend code).
- OQ-7 — Toast fallback string when ApiError.message is empty/HTML (resolve in /spec).

## Doc gaps to apply (post-grill loop 2)

1. **Backend Defect subsection** for Q-3 with live repro + traceback.
2. **Configurable wpm constant** — new requirement on Settings → TTS surface (default 200) and on the listen-time formula.
3. **Voice pre-warm** — new FR for AudioTab mount behaviour.
4. **Toast lifecycle contract** — new FR (sticky/4s/dedupe/clear-on-retry-success).
5. **Engine picker for populated audio state** — new FR; updates J2/J3 to cover post-generation flow.
6. **Partial-state Generate estimate semantics** — extend D3 with delta-vs-total clarification.
7. **D6 reversal** — rewrite Decisions row D6; update G6 measurement to require comparison-button presence.

## Recommended next step

Apply the 7 gaps above to `01_requirements.md` directly, then advance to **Phase 4.a `/msf-req`** (Tier 3: Recommended).

---

## Process notes

- 8 questions asked, 0 deferred, 0 user overrides on Recommended (all picked Recommended; one customised — Q2 raised wpm 150→200 and added the Settings-knob requirement).
- Codebase resolved 1 OQ (OQ-6) without asking the user, by reading `SpikeFindingsBlock.vue` directly — saved a turn and produced a stronger conclusion (D6 reversal) than the user-facing question would have.
- The grill surfaced 1 gap NOT in the original OQ list: populated-audio-state behavior after generation (Q5). This was inferable from D2's empty-state-only framing — the doc described the empty state but not the transition.
