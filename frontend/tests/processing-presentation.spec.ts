import { expect, test } from '@playwright/test'

// Presentation-only fixtures: no candidate records, uploads or AI calls.
for (const width of [390, 768, 1024, 1440]) test(`focused processing and completed profile at ${width}px`, async ({ page }, info) => {
  await page.setViewportSize({ width, height: 900 })
  await page.emulateMedia({ reducedMotion: width === 390 || width === 1440 ? 'reduce' : 'no-preference' })
  let done = false
  const resume = { id: 2, original_name: 'Fictional-Engineer.pdf', version: 2, processing_status: 'processing', scan_status: 'scanning', processing_error: '', can_retry: false, uploaded_at: '2026-10-21T10:00:00Z', url: null }
  const completed = { ...resume, processing_status: 'completed', scan_status: 'clean' }
  const profile = { id: 9001, full_name: 'Fictional Test Candidate', email: 'fictional@example.com', headline: 'Backend Engineer', total_experience: '5', skills: ['Python', 'Django'], education: [], work_preferences: [], work_experiences: [], career_preferences: {}, meaningful_work: '', submission_missing_fields: [], can_submit: false, profile_status: 'draft', available_resume: completed }
  await page.route('**/api/v1/**', route => {
    const path = new URL(route.request().url()).pathname
    if (path.endsWith('/auth/me/')) return route.fulfill({ json: { id: 9001, role: 'candidate', full_name: profile.full_name, email: profile.email } })
    if (path.endsWith('/candidate/profile/')) return route.fulfill({ json: { ...profile, latest_resume: done ? completed : resume } })
    if (path.endsWith('/candidate/resume-status/')) return route.fulfill({ json: { resume: done ? completed : resume, worker_available: true } })
    return route.fulfill({ json: {} })
  })
  await page.route('**/*.mp4', route => route.abort())
  await page.goto('/')
  const card = page.getByRole('region', { name: "While we get to know you…" })
  await expect(card).toBeVisible()
  await expect(page.getByRole('complementary', { name: 'Career Settings panel' })).toHaveCount(0)
  await expect(page.locator('.cp-profile-workspace')).toHaveCount(0)
  await expect(card).toContainText('Scanning — checking your file safely.')
  await expect(page.locator('.cp-processing-bar span')).toHaveCSS('animation-name', width === 390 || width === 1440 ? 'none' : 'cp-processing-sweep')
  const bounds = await card.boundingBox()
  expect(bounds!.width).toBeLessThanOrEqual(560)
  expect(await card.evaluate(el => parseFloat(getComputedStyle(el).paddingLeft))).toBeGreaterThanOrEqual(24)
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
  await page.screenshot({ path: info.outputPath(`processing-${width}.png`) })
  done = true
  await expect(card).toHaveCount(0, { timeout: 20000 })
  await expect(page.getByRole('complementary', { name: 'Career Settings panel' })).toBeVisible()
  await expect(page.locator('.cp-identity')).toContainText('Fictional Test Candidate')
  await page.screenshot({ path: info.outputPath(`profile-${width}.png`) })
})

test('Kindred uses transparent monochrome artwork in the logo row', async ({ page }, info) => {
  await page.route('**/api/v1/**', route => route.fulfill({ status: 401, json: {} }))
  await page.goto('/')
  const logo = page.getByRole('button', { name: 'About Kindred Group', exact: true })
  await logo.focus()
  const img = logo.locator('img')
  await expect(img).toHaveAttribute('src', /kindred-transparent/)
  await expect.poll(() => img.evaluate(el => (el as HTMLImageElement).complete && (el as HTMLImageElement).naturalWidth > 0)).toBe(true)
  // Render the actual SVG into a canvas: its white corner must now be transparent.
  expect(await img.evaluate(el => {
    const canvas = document.createElement('canvas'); canvas.width = 217; canvas.height = 64
    const ctx = canvas.getContext('2d')!; ctx.drawImage(el as HTMLImageElement, 0, 0, 217, 64)
    return ctx.getImageData(0, 0, 1, 1).data[3]
  })).toBe(0)
  await page.screenshot({ path: info.outputPath('logo-strip.png') })
})
