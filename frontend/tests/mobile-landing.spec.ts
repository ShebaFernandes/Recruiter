import { devices, expect, test } from '@playwright/test'

test.use({ ...devices['Pixel 7'], deviceScaleFactor: 1, defaultBrowserType: 'chromium' })

test.beforeEach(async ({ page }) => {
  await page.addInitScript(() => sessionStorage.setItem('enter-door-intro-seen', '1'))
})

for (const width of [360, 390, 430, 1440]) {
  test.describe(`${width}px viewport`, () => {
  test.use(width === 1440 ? { isMobile: false, hasTouch: false, userAgent: devices['Desktop Chrome'].userAgent } : {})
  test(`landing remains readable and unclipped at ${width}px`, async ({ page }, testInfo) => {
    const height = width === 1440 ? 900 : 844
    await page.setViewportSize({ width, height })
    await page.goto('/')
    await page.evaluate(() => document.fonts.ready)
    await page.locator('.landing-background img, .ce-logo img').evaluateAll(async images => {
      await Promise.all(images.map(image => (image as HTMLImageElement).decode()))
    })

    const heading = page.getByRole('heading', { name: 'The best teams are built by ENTER.' })
    const candidateNav = page.getByTestId('for-candidates')
    const motion = page.getByRole('button', { name: 'Pause background animation' })
    await expect(heading).toBeVisible()
    await expect(candidateNav).toBeVisible()
    await expect(motion).toBeVisible()
    if (process.env.EXPECT_CANDIDATE_ONLY === 'true') {
      await expect(page.getByTestId('for-recruiters')).toHaveCount(0)
    }
    expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(width)

    await expect(page.locator('.ce-intro').getByRole('button', { name: 'For Companies' })).toBeVisible()
    await expect(page.locator('.ce-intro').getByRole('button', { name: 'For Candidates' })).toBeVisible()
    for (const section of ['#what-building-title', '#closing-section']) {
      await page.locator(section).scrollIntoViewIfNeeded()
    }
    await expect(page.getByRole('link', { name: 'Privacy', exact: true })).toHaveAttribute('href', '/privacy')
    await expect(page.getByRole('link', { name: 'Terms', exact: true })).toHaveAttribute('href', '/terms')
    await expect(page.getByRole('link', { name: 'Contact', exact: true })).toHaveAttribute('href', 'mailto:sheba@enterrecruitment.com')
    expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(width)
    await page.evaluate(() => window.scrollTo(0, 0))

    await motion.click()
    await expect(page.locator('.landing-background__scene')).toHaveCSS('animation-play-state', 'paused')
    await page.screenshot({ path: testInfo.outputPath(`landing-${width}.png`), fullPage: true, animations: 'disabled' })
    await page.getByRole('button', { name: 'Play background animation' }).click()
    await expect(page.locator('.landing-background__scene')).toHaveCSS('animation-play-state', 'running')
  })
  })
}

test('mobile navigation retains candidate signup and login', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 })
  await page.goto('/')
  await page.getByText('Log in', { exact: true }).click()
  if (process.env.EXPECT_CANDIDATE_ONLY === 'true') {
    await expect(page.getByRole('button', { name: 'Recruiter log in' })).toHaveCount(0)
  }
  await page.getByRole('button', { name: 'Candidate log in' }).click()
  await expect(page.getByRole('heading', { name: 'Welcome back' })).toBeVisible()
  await page.goto('/')
  await page.getByTestId('for-candidates').click()
  await expect(page.getByRole('heading', { name: 'Create your account' })).toBeVisible()
})

test('reduced motion keeps the mobile landing static and candidate navigation usable', async ({ page }) => {
  await page.emulateMedia({ reducedMotion: 'reduce' })
  await page.setViewportSize({ width: 390, height: 844 })
  await page.goto('/')
  await expect(page.getByTestId('for-candidates')).toBeVisible()
  await expect(page.locator('.ce-intro').getByRole('button', { name: 'For Candidates' })).toBeVisible()
  await expect(page.getByRole('button', { name: 'Pause background animation' })).toHaveCount(0)
  await expect(page.locator('.landing-background__scene')).toHaveCSS('animation-name', 'none')
})
