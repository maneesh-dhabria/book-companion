# Journeys reviewed

## J1 — Quiz feature (first-time UX → start → generation → QnA)

Entry context: signed-in user, on a book where all 12 sections are summarized, no prior quiz session. Medium intent (40).

| Step | URL / action                                               | Screen file                       |
| ---- | ---------------------------------------------------------- | --------------------------------- |
| 1    | Land on Quiz tab                                           | `01-quiz-firstvisit.png`          |
| 2    | Click *Start quiz* (default scope = All summaries)         | `02-quiz-generating.png`          |
| 3    | Wait 3s for question to appear                             | `03-quiz-question.png` (no transition; backend 500) |
| 4    | Switch scope to *Specific chapters*                        | `04-quiz-scopepicker.png`         |
| 5    | QnA experience (question card / answer textarea / scoring) | **DEFERRED — backend 500 prevented observation in this session** |

## J2 — Audio feature (first-time UX → engine confusion → generate dialog)

Entry context: same book, same user, no audio generated yet. Medium intent (40).

| Step | URL / action                          | Screen file                          |
| ---- | ------------------------------------- | ------------------------------------ |
| 1    | Land on Audio tab                     | `05-audio-firstvisit.png`            |
| 2    | Open *What's the difference?* tooltip | `06-audio-difference.png`            |
| 3    | Click *Generate audio* (Kokoro modal) | `07-audio-generate-clicked.png`      |
| 4    | Open audio settings                   | `08-audio-settings.png`              |
