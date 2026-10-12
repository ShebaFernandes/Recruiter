import { expect, test, type Page } from '@playwright/test'

// UI boundary tests: no live provider calls. Django tests exercise the actual
// provider schema, signed state, CSRF, quotas and private API permissions.
async function mockGuestAPI(page: Page, limited = false) {
  const privateRequests: string[] = []
  const calls: string[] = []
  await page.route('**/api/v1/**', async route => {
    const path = new URL(route.request().url()).pathname.replace('/api/v1/', '')
    if (path === 'auth/me/') return route.fulfill({ status: 401, json: { detail: 'Not authenticated.' } })
    if (path === 'auth/csrf/') return route.fulfill({ json: { csrfToken: 'test-csrf' } })
    if (path === 'guest/searches/' || path === 'guest/searches/answer/') {
      calls.push(path)
      expect(route.request().headers()['x-csrftoken']).toBe('test-csrf')
      if (limited) return route.fulfill({ status: 429, headers: { 'Retry-After': '60' }, json: { code: 'guest_search_limited', detail: 'Guest search has reached its request limit. Please try again later.' } })
      const answering = path.endsWith('/answer/')
      if (answering) expect(route.request().postDataJSON().token).toBe('signed-test-state')
      return route.fulfill({ json: {
        id: 'guest', token: 'signed-test-state', query: 'Backend engineer with 4 years experience',
        state: answering ? 'complete' : 'needs_clarification',
        criteria: { role: 'Backend engineer', min_experience: 4, location: '', max_salary_lpa: null, notice_period_days: null, remote_ok: answering },
        follow_up_question: answering ? '' : 'Are remote candidates okay?',
        follow_up_options: answering ? [] : ['Remote', 'Let me type it'],
        understanding_source: 'openrouter', understanding_model: 'mock-test-model',
      } })
    }
    privateRequests.push(path)
    return route.fulfill({ status: 403, json: { detail: 'Protected.' } })
  })
  return { privateRequests, calls }
}

for (const width of [1440, 1024, 390]) {
  test(`guest search and clarification at ${width}px never request private records`, async ({ page }, info) => {
    const evidence = await mockGuestAPI(page)
    await page.setViewportSize({ width, height: 900 })
    await page.goto('/')
    await expect(page.getByRole('navigation', { name: 'Main navigation' }).getByText('Log in')).toHaveCount(0)
    await page.getByTestId('for-recruiters').click()
    await expect(page).toHaveURL(/\/recruiter$/)
    await expect(page.getByRole('heading', { name: 'Who are we hiring today?' })).toBeVisible()
    await expect(page.getByLabel('Password', { exact: true })).toHaveCount(0)
    await page.reload()
    await page.getByLabel('Candidate search', { exact: true }).fill('Backend engineer with 4 years experience')
    await page.getByLabel('Candidate search', { exact: true }).press('Enter')
    await expect(page.getByText('Are remote candidates okay?')).toBeVisible()
    expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(width)
    await page.screenshot({ path: info.outputPath(`guest-clarification-${width}.png`), fullPage: true })
    const remote = page.getByRole('button', { name: 'Remote', exact: true })
    await remote.focus()
    await remote.press('Enter')
    const completed = page.getByRole('heading', { name: 'Your search brief is ready' })
    await expect(completed).toBeFocused()
    await expect(page.getByText(/Candidate profiles, resumes, contact details/)).toBeVisible()
    await expect(page.locator('.candidate-card')).toHaveCount(0)
    expect(evidence.calls).toEqual(['guest/searches/', 'guest/searches/answer/'])
    expect(evidence.privateRequests).toEqual([])
    expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(width)
    await page.screenshot({ path: info.outputPath(`guest-brief-${width}.png`), fullPage: true })
    await page.getByRole('button', { name: 'Open protected recruiter workspace' }).click()
    await expect(page.getByRole('heading', { name: 'Create your account' })).toBeVisible()
    await page.getByRole('button', { name: /Already have an account/ }).click()
    await expect(page.getByRole('heading', { name: 'Welcome back' })).toBeVisible()
    await page.goBack()
    await expect(page.getByRole('heading', { name: 'Who are we hiring today?' })).toBeVisible()
    expect(evidence.calls).toHaveLength(2)
  })
}

test('rate limit does not cause retry loops and candidate login stays available', async ({ page }) => {
  const evidence = await mockGuestAPI(page, true)
  await page.emulateMedia({ reducedMotion: 'reduce' })
  await page.goto('/recruiter')
  await page.getByLabel('Candidate search', { exact: true }).fill('Backend engineer')
  await page.getByRole('button', { name: 'Search talent' }).click()
  await expect(page.getByRole('alert')).toContainText('request limit')
  await expect(page.getByRole('button', { name: 'Search talent' })).toBeEnabled()
  expect(evidence.calls).toHaveLength(1)
  await page.getByRole('button', { name: 'Back to Enter', exact: true }).click()
  await page.getByTestId('for-candidates').click()
  await expect(page.getByRole('heading', { name: 'Create your account' })).toBeVisible()
  await page.getByRole('button', { name: /Already have an account/ }).click()
  await expect(page.getByRole('heading', { name: 'Welcome back' })).toBeVisible()
  expect(evidence.privateRequests).toEqual([])
})
