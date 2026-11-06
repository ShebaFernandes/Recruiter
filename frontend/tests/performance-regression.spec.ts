import { expect, test } from '@playwright/test'

// These checks never write to the backend. Authentication POSTs receive synthetic responses.
for (const width of [390, 1440]) {
  test(`public pages, responsive artwork and candidate entry at ${width}`, async ({ page }, info) => {
    test.setTimeout(90_000)
    await page.setViewportSize({ width, height: 900 })
    await page.emulateMedia({ reducedMotion: 'reduce' })
    await page.route('**/api/v1/**', async route => {
      const pathname = new URL(route.request().url()).pathname
      if (pathname.endsWith('/auth/me/')) return route.fulfill({ status: 401, json: {} })
      if (pathname.endsWith('/auth/csrf/')) return route.fulfill({ json: { csrfToken: 'synthetic-only' } })
      if (pathname.endsWith('/auth/login/')) return route.fulfill({ status: 400, json: { detail: 'Synthetic login exercised safely.' } })
      if (route.request().method() !== 'GET') return route.abort()
      return route.fallback()
    })
    const artworkRequests: string[] = []
    page.on('request', request => { if (/hiring-enquiry-landscape|ambition-hires-mountain/.test(request.url())) artworkRequests.push(request.url()) })
    const videos: string[] = []
    page.on('request', request => { if (request.url().includes('.mp4')) videos.push(request.url()) })
    await page.goto('/')
    await expect(page.locator('#ce-title')).toBeVisible()
    await page.evaluate(() => document.fonts.ready)
    await expect(page.locator('.landing-background img')).toHaveCount(6)
    await page.locator('.landing-background img').evaluateAll(images => Promise.all(images.map(image => (image as HTMLImageElement).decode())))
    await page.screenshot({ path: info.outputPath(`landing-${width}.png`), animations: 'disabled' })
    expect(videos).toEqual([])
    expect(artworkRequests).toEqual([])
    await page.getByTestId('for-companies').click()
    await expect(page.locator('#what-building-title')).toBeInViewport()
    for (const image of await page.locator('.growth-stages__grid img').all()) {
      await image.scrollIntoViewIfNeeded()
      await image.evaluate(image => (image as HTMLImageElement).decode())
      expect(await image.evaluate(image => (image as HTMLImageElement).naturalWidth)).toBeGreaterThan(0)
    }
    await page.locator('.evidence-to-hires').scrollIntoViewIfNeeded()
    await expect(page.locator('.evidence-to-hires')).toHaveAttribute('data-artwork-ready', 'true')
    await page.locator('.evidence-to-hires').evaluate(async element => {
      const background = getComputedStyle(element, '::before').backgroundImage
      const url = background.match(/url\(["']?([^"')]+)["']?\)/)?.[1]
      if (!url) throw new Error('Evidence landscape missing')
      const image = new Image(); image.src = url; await image.decode()
    })
    await page.locator('.closing-cta').scrollIntoViewIfNeeded()
    await page.locator('.closing-cta__landscape').evaluate(image => (image as HTMLImageElement).decode())
    await page.screenshot({ path: info.outputPath(`closing-${width}.png`), animations: 'disabled' })
    expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(width)
    await page.getByRole('button', { name: 'Create an account', exact: true }).click()
    await expect(page.getByRole('heading', { name: 'Create your account' })).toBeVisible()
    await expect(page.getByLabel('Full name')).toBeVisible()
    await page.getByRole('button', { name: /Already have an account/ }).click()
    await expect(page.getByRole('heading', { name: 'Welcome back' })).toBeVisible()
    await page.getByLabel('Email', { exact: true }).fill('performance-synthetic@example.com')
    await page.getByLabel('Password', { exact: true }).fill('Synthetic-only-123!')
    await page.getByRole('button', { name: 'Log in', exact: true }).click()
    await expect(page.getByText('Synthetic login exercised safely.')).toBeVisible()
    await page.screenshot({ path: info.outputPath(`login-${width}.png`), animations: 'disabled' })
    for (const path of ['/careers', '/opportunities']) {
      await page.goto(path)
      await expect(page.locator('h1')).toBeVisible()
      expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(width)
      await page.screenshot({ path: info.outputPath(`${path.slice(1)}-${width}.png`), animations: 'disabled' })
    }
  })
}

test('synthetic login, resume upload and saved Career Journey survive deferred loading', async ({ page }) => {
  const user = { id: 99999, email: 'performance-synthetic@example.com', role: 'candidate', full_name: 'Synthetic Candidate' }
  let profile = { id: 99999, full_name: user.full_name, email: user.email, headline: 'Engineer', current_company: '', location: 'Bengaluru', total_experience: '2', summary: '', meaningful_work: '', skills: ['TypeScript'], education: [], work_preferences: [], work_experiences: [] as object[], career_preferences: {}, profile_updated_at: 'synthetic-v1', profile_status: 'draft', submission_missing_fields: [], missing_fields: [], can_submit: false, latest_resume: null as object | null }
  let uploaded = false
  let loggedIn = false
  await page.route('**/api/v1/**', async route => {
    const path = new URL(route.request().url()).pathname
    if (path.endsWith('/auth/me/')) return route.fulfill({ status: loggedIn ? 200 : 401, json: loggedIn ? user : {} })
    if (path.endsWith('/auth/csrf/')) return route.fulfill({ json: { csrfToken: 'synthetic-only' } })
    if (path.endsWith('/auth/login/')) { loggedIn = true; return route.fulfill({ json: { user } }) }
    if (path.endsWith('/candidate/profile/')) return route.fulfill({ json: profile })
    if (path.endsWith('/candidate/resumes/') && route.request().method() === 'POST') {
      uploaded = route.request().postDataBuffer()?.includes(Buffer.from('synthetic.pdf')) || false
      profile = { ...profile, latest_resume: { id: 99999, original_name: 'synthetic.pdf', version: 1, uploaded_at: '2026-01-01', processing_status: 'completed', scan_status: 'clean', url: null, processing_error: '', can_retry: false }, work_experiences: [{ id: 99999, company: 'Synthetic Systems', role: 'Engineer', start_date: '2024-01-01', end_date: null, is_current: true, description: '', gap_reason: '' }] }
      return route.fulfill({ status: 202, json: profile })
    }
    if (route.request().method() !== 'GET') return route.abort()
    return route.fallback()
  })
  await page.goto('/')
  await page.getByRole('button', { name: 'Create an account', exact: true }).click()
  await page.getByRole('button', { name: /Already have an account/ }).click()
  await page.getByLabel('Email', { exact: true }).fill(user.email)
  await page.getByLabel('Password', { exact: true }).fill('Synthetic-only-123!')
  await page.getByRole('button', { name: 'Log in', exact: true }).click()
  await expect(page.getByTestId('resume-input')).toBeAttached()
  await page.getByTestId('resume-input').setInputFiles({ name: 'synthetic.pdf', mimeType: 'application/pdf', buffer: Buffer.from('%PDF-1.4 synthetic frontend transport fixture') })
  await expect(page.getByRole('heading', { name: 'Your career journey', exact: true })).toBeVisible()
  await expect(page.getByRole('button', { name: /Engineer at Synthetic Systems/ })).toBeVisible()
  expect(uploaded).toBe(true)
})
