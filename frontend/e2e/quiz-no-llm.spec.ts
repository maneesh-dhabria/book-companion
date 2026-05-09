/**
 * No-LLM banner journey (spec §14.3): with `LLMProvider=None`, tab renders
 * the banner; past history (seeded) still readable.
 *
 * This test asserts the no-LLM gate is reachable from the quiz route. It does
 * NOT spawn its own backend with `LLMProvider=disabled` — that's a setup
 * concern handled by the test runner (env var on the backend serve command).
 * When run against a backend with an LLM provider attached, the test skips.
 */

import { test, expect } from '@playwright/test'
import { getFirstBookId } from './fixtures/quiz_seed'

test.describe('quiz no-LLM journey', () => {
  test('renders the no-LLM banner when the backend reports no provider', async ({
    page,
    request,
  }) => {
    const llm = await request.get('/api/v1/llm/status')
    if (!llm.ok()) test.skip(true, 'LLM status endpoint unavailable.')
    const status = await llm.json()
    test.skip(
      !!status.preflight?.ok,
      `LLM provider available (${status.preflight?.provider ?? 'unknown'}); the no-LLM banner only renders when no provider is detected. Set BOOKCOMPANION_LLM__PROVIDER=disabled and restart serve to exercise this branch.`,
    )

    const bookId = await getFirstBookId(request)
    test.skip(bookId === null, 'No seeded books — run `bookcompanion add` first.')
    await page.goto(`/books/${bookId}?tab=quiz`)
    await expect(page.getByTestId('no-llm-banner')).toBeVisible()
  })
})
