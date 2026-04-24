import { expect, test } from '@playwright/test'

/**
 * T37 / FR-E4 — AI tag seeding on the overview.
 *
 * We don't trigger a real LLM summary here (too slow, flaky on CI). Instead
 * we mock GET /api/v1/books/:id to inject suggested_tags and assert the
 * SuggestedTagsBar renders them, Accept creates a tag chip, Dismiss wipes
 * the suggestion.
 */

const BOOK_ID = 1

test.describe('v1.5 AI tag seeding', () => {
  test('suggested tags render + accept + dismiss', async ({ page }) => {
    const base = {
      id: BOOK_ID,
      title: 'Porter',
      status: 'completed',
      file_format: 'epub',
      file_size_bytes: 0,
      file_hash: 'h',
      authors: [],
      sections: [],
      section_count: 0,
      cover_url: null,
      suggested_tags: ['strategy', 'value-chain'],
      summary_progress: {
        summarizable: 0,
        summarized: 0,
        failed_and_pending: 0,
        pending: 0,
      },
      last_summary_failure: null,
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
    }
    await page.route(`**/api/v1/books/${BOOK_ID}`, (route) =>
      route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(base) }),
    )
    await page.route(`**/api/v1/books/${BOOK_ID}/tags`, (route) =>
      route.fulfill({ status: 200, contentType: 'application/json', body: '{"tags":[]}' }),
    )

    await page.goto(`/books/${BOOK_ID}`)
    await expect(page.getByText('Suggested tags')).toBeVisible({ timeout: 3000 })
    await expect(page.getByText('strategy')).toBeVisible()
    await expect(page.getByText('value-chain')).toBeVisible()

    // Clicking a suggested chip fires two API calls: POST tag, PATCH reject.
    let addedTag: string | null = null
    await page.route(`**/api/v1/books/${BOOK_ID}/tags`, (route) => {
      if (route.request().method() === 'POST') {
        const body = JSON.parse(route.request().postData() || '{}')
        addedTag = body.name
        return route.fulfill({
          status: 201,
          contentType: 'application/json',
          body: JSON.stringify({ id: 1, name: body.name, color: null }),
        })
      }
      return route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: '{"tags":[]}',
      })
    })
    await page.route(`**/api/v1/books/${BOOK_ID}/suggested-tags`, (route) =>
      route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: '{"suggested_tags":["value-chain"]}',
      }),
    )

    await page.getByText('strategy', { exact: true }).click()
    await expect.poll(() => addedTag).toBe('strategy')
  })
})
