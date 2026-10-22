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

    await expect(page.locator('.ce-intro button')).toHaveCount(0)
    if (width <= 768) {
      await expect(heading).toHaveCSS('color', 'rgb(11, 31, 58)')
      await expect(candidateNav).toHaveCSS('color', 'rgb(11, 31, 58)')
      const layout = await page.evaluate(viewportHeight => {
        const box = (selector: string) => {
          const bounds = document.querySelector(selector)!.getBoundingClientRect()
          return { top: bounds.top, right: bounds.right, bottom: bounds.bottom, left: bounds.left, width: bounds.width }
        }
        return {
          heading: box('.ce-intro h1'),
          copy: box('.ce-intro-aside'),
          motion: box('.landing-motion-toggle'),
          viewportHeight,
        }
      }, height)
      expect(layout.heading.left + layout.heading.width / 2).toBeCloseTo(width / 2, 0)
      expect(layout.copy.top).toBeGreaterThan(layout.heading.bottom)
      expect(layout.copy.bottom).toBeLessThan(layout.viewportHeight * .55)
      expect(layout.motion.top).toBeGreaterThan(layout.copy.bottom)
    } else {
      await expect(heading).toHaveCSS('color', 'rgb(48, 56, 66)')
    }

    await motion.click()
    await expect(page.locator('.landing-background__scene')).toHaveCSS('animation-play-state', 'paused')
    await page.screenshot({ path: testInfo.outputPath(`landing-${width}.png`), fullPage: true, animations: 'disabled' })
    await page.getByRole('button', { name: 'Play background animation' }).click()
    await expect(page.locator('.landing-background__scene')).toHaveCSS('animation-play-state', 'running')
  })
  })
}

test('mobile navigation retains candidate signup and login without hero buttons', async ({ page }) => {
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
  await expect(page.locator('.ce-intro button')).toHaveCount(0)
  await expect(page.getByRole('button', { name: 'Pause background animation' })).toHaveCount(0)
  await expect(page.locator('.landing-background__scene')).toHaveCSS('animation-name', 'none')
})
