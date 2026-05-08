# Source

- Type: url (live app)
- Location: http://localhost:8000/
- Auth: none (single-user local tool)
- Stack: FastAPI backend serving built Vue 3 SPA from `backend/app/static/`
- Library state: ≥1 book seeded — book id 1 = "Understanding Michael Porter" (Magretta)
- Backend health: `{status:ok, llm_provider:claude, llm_available:true}`

## Routes captured

- `/` — Library page
- `/books/1` — BookSummaryPage
- `/books/1/sections/3` — SectionDetailPage (Introduction)
- Audio playback — invoked via "Listen" button on BookSummaryPage / SectionDetailPage
