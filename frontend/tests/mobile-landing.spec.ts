import { expect, test } from '@playwright/test'

test.beforeEach(async ({ page }) => {
  await page.addInitScript(() => sessionStorage.setItem('enter-door-intro-seen', '1'))
})

for (const width of [360, 390, 430, 768, 1440]) {
  test(`landing remains readable and unclipped at ${width}px`, async ({ page }, testInfo) => {
    const height = width === 1440 ? 900 : 844
    await page.setViewportSize({ width, height })
    await page.goto('/')
    await page.evaluate(() => document.fonts.ready)

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

    const cta = page.getByRole('button', { name: 'Upload your resume' })
    if (width <= 768) {
      await expect(cta).toBeVisible()
      await expect(heading).toHaveCSS('color', 'rgb(11, 31, 58)')
      await expect(candidateNav).toHaveCSS('color', 'rgb(11, 31, 58)')
      const layout = await page.evaluate(viewportHeight => {
        const box = (selector: string) => {
          const bounds = document.querySelector(selector)!.getBoundingClientRect()
          return { top: bounds.top, right: bounds.right, bottom: bounds.bottom, left: bounds.left, width: bounds.width }
        }
        return {
          heading: box('.ce-intro h1'),
          cta: box('.ce-mobile-candidate-cta'),
          motion: box('.landing-motion-toggle'),
          viewportHeight,
        }
      }, height)
      expect(layout.heading.left + layout.heading.width / 2).toBeCloseTo(width / 2, 0)
      expect(layout.cta.top).toBeGreaterThan(layout.heading.bottom)
      expect(layout.cta.bottom).toBeLessThanOrEqual(layout.viewportHeight)
      const overlaps = !(layout.cta.right <= layout.motion.left || layout.motion.right <= layout.cta.left || layout.cta.bottom <= layout.motion.top || layout.motion.bottom <= layout.cta.top)
      expect(overlaps).toBe(false)
    } else {
      await expect(cta).toBeHidden()
      await expect(heading).toHaveCSS('color', 'rgb(48, 56, 66)')
    }

    await page.screenshot({ path: testInfo.outputPath(`landing-${width}.png`), fullPage: true, animations: 'disabled' })
  })
}

test('mobile resume CTA opens the existing candidate signup flow', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 })
  await page.goto('/')
  await page.getByRole('button', { name: 'Upload your resume' }).click()
  await expect(page.getByRole('heading', { name: 'Create your account' })).toBeVisible()
})

test('reduced motion keeps the mobile landing static without hiding its CTA', async ({ page }) => {
  await page.emulateMedia({ reducedMotion: 'reduce' })
  await page.setViewportSize({ width: 390, height: 844 })
  await page.goto('/')
  await expect(page.getByRole('button', { name: 'Upload your resume' })).toBeVisible()
  await expect(page.getByRole('button', { name: 'Pause background animation' })).toHaveCount(0)
  await expect(page.locator('.landing-background__scene')).toHaveCSS('animation-name', 'none')
})
