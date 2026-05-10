# Source

- **Type:** live URL (running app)
- **Location:** `http://localhost:8000/books/1` (book: *Understanding Michael Porter* — 12 sections, all summarized)
- **Auth:** none (single-user local server)
- **Backend:** uvicorn 200 OK; Claude provider preflight ok (claude 2.1.138)
- **Console errors observed during capture:**
  - `GET /api/v1/audio/positions/by-book/1 → 404` (every page load on book 1)
  - `POST /api/v1/books/1/quiz-sessions → 500` (every Start-quiz click — backend bug; surfaces as silent failure in UI; see finding Q-3)
