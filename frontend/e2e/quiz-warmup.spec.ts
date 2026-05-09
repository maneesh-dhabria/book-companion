/**
 * Warm-up journey (spec §14.3): seed a prior session with a Missed
 * concept_label → reopen tab → warm-up banner appears → first question is a
 * fresh stem on that concept.
 */

import { test, expect } from '@playwright/test'

test.describe('quiz warm-up journey', () => {
  test.fixme(
    'warm-up banner enumerates Missed/Partial concepts (FR-72)',
    async ({ page }) => {
      // TODO: pre-populate quiz_questions with a prior session at
      //       self_assessment='missed' and concept_label='loss aversion'
      //       via a sqlite shell, then reopen the Quiz tab and assert the
      //       warm-up banner names that concept.
      await page.goto('/books/1?tab=quiz')
      await page.getByRole('button', { name: /start quiz/i }).click()
      await expect(page.getByTestId('warm-up-banner')).toBeVisible()
      await expect(page.getByTestId('warm-up-banner')).toContainText(/loss aversion/i)
    },
  )
})
