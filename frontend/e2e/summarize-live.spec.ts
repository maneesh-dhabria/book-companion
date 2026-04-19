import { expect, test } from '@playwright/test'

const BASE = process.env.BC_BASE_URL ?? 'http://localhost:8765'
const BOOK_ID = Number(process.env.BC_BOOK_ID ?? 1)

test.use({ baseURL: BASE })

test.describe.configure({ timeout: 600_000 })

test('Summarize this section → Generating → rendered summary (live LLM)', async ({
  page,
}) => {
  const sseEvents: Array<{ event: string; data: unknown }> = []
  page.on('console', (msg) => {
    const text = msg.text()
    if (msg.type() === 'error') console.log('BROWSER_ERR:', text)
    if (text.includes('[reader]') || text.includes('updateSection')) {
      console.log('BROWSER_LOG:', text)
    }
  })

  await page.goto(`/books/${BOOK_ID}`)
  await page.waitForLoadState('networkidle')

  // Capture SSE events at the network level — EventSource doesn't show in
  // request logs the same way, but the SSE stream is a normal fetch.
  page.on('response', async (resp) => {
    const url = resp.url()
    if (url.includes('/processing/') && url.endsWith('/stream')) {
      console.log('SSE OPENED:', resp.status())
    }
  })

  // Navigate to a chapter without a summary via TOC
  await page.locator('.toc-trigger').click()
  const chapterLink = page
    .locator('.toc-list > .toc-item')
    .filter({ hasText: 'Chapter I. LAYING PLANS' })
    .first()
  await chapterLink.click()
  await page.waitForLoadState('networkidle')

  // Switch to Summary tab (if not already active — button is disabled when active)
  const summaryBtn = page.getByRole('button', { name: /^Summary$/i }).first()
  const isDisabled = await summaryBtn.isDisabled()
  if (!isDisabled) {
    await summaryBtn.click()
  }
  await expect(page.getByText(/Not yet summarized/i)).toBeVisible()

  const cta = page.getByRole('button', { name: /Summarize this section/i })
  await expect(cta).toBeVisible()

  // Fire the real summarization. Listen to the /summarize POST response
  // to capture the job_id so we can assert on final state.
  const [postResp] = await Promise.all([
    page.waitForResponse(
      (r) => r.url().includes('/api/v1/books/') && r.url().endsWith('/summarize') && r.request().method() === 'POST',
    ),
    cta.click(),
  ])
  expect(postResp.ok()).toBe(true)
  const job = (await postResp.json()) as { job_id: number }
  console.log('JOB STARTED:', job.job_id)

  // Frontend enters "Generating summary…" state
  await expect(page.getByText(/Generating summary/i)).toBeVisible({ timeout: 15_000 })

  // Poll backend until the summary is persisted.
  await expect
    .poll(
      async () => {
        const r = await fetch(`${BASE}/api/v1/books/${BOOK_ID}/sections/14`)
        const j = await r.json()
        return j.default_summary?.summary_md ? 'ready' : 'waiting'
      },
      { timeout: 420_000, intervals: [2_000] },
    )
    .toBe('ready')

  // Give the SSE handler a chance to update the reader store.
  await page.waitForTimeout(2_000)

  // Diagnostic: read the Pinia store state directly to distinguish
  // "SSE updated store → template didn't rerender" from "SSE never updated store".
  const storeState = await page.evaluate(() => {
    const w = window as unknown as {
      __piniaStores?: Record<string, { $state: Record<string, unknown> }>
    }
    // Vue devtools exposes __pinia via the app; fall back to reading DOM.
    return {
      url: location.href,
      readingAreaCount: document.querySelectorAll('.reading-area').length,
      emptyStateCount: document.querySelectorAll('.summary-empty').length,
      emptyStateText: document.querySelector('.summary-empty')?.textContent?.trim() ?? null,
      piniaAvailable: Boolean(w.__piniaStores),
    }
  })
  console.log('STORE PROBE:', JSON.stringify(storeState))

  // UI should now render the summary via ReadingArea.
  await expect(page.locator('.reading-area').first()).toBeVisible({ timeout: 15_000 })

  // Verify the reading area now shows non-empty summary-like content
  const readingText = (await page.locator('.reading-area').first().innerText()).trim()
  expect(readingText.length).toBeGreaterThan(50)
  // "Not yet summarized" must be gone
  await expect(page.getByText(/Not yet summarized/i)).toHaveCount(0)

  // Book-level progress counter should have incremented by at least 1
  const progressText = await page
    .getByText(/\d+ of \d+ sections summarized/)
    .first()
    .textContent()
  const match = progressText?.match(/(\d+) of (\d+)/)
  expect(match).not.toBeNull()
  expect(Number(match![1])).toBeGreaterThanOrEqual(1)

  await page.screenshot({
    path: 'e2e/artifacts/ux-polish-after-summarize.png',
    fullPage: true,
  })
})
