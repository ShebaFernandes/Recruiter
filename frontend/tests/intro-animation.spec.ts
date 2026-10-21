import { test, expect } from '@playwright/test'
test.use({ video:{ mode:'on', size:{ width:1440, height:1000 } } })
test.beforeEach(async ({ page }) => {
  await page.route('**/api/v1/auth/me/', route => route.fulfill({ status:401, json:{ detail:'Not authenticated' } }))
})
for (const width of [390,768,1024,1440]) {
  test(`automatic entrance and landing at ${width}px`, async ({ page }, info) => {
    await page.setViewportSize({ width,height:900 })
    const errors:string[] = []
    page.on('pageerror', error => errors.push(error.message))
    await page.goto('/')
    await expect(page.getByRole('region', { name:'Welcome to ENTER' })).toBeVisible()
    await expect(page.getByText('Scroll to enter')).toHaveCount(0)
    await expect.poll(() => page.locator('.enter-intro-shell').getAttribute('data-progress').then(Number)).toBeGreaterThan(.3)
    await page.screenshot({ path:info.outputPath(`door-${width}.png`) })
    await expect(page.locator('.enter-intro-track')).toHaveCount(0, { timeout:5500 })
    await expect(page.locator('#enter-home')).toBeFocused()
    await expect(page.locator('.ce-intro h1')).toHaveCSS('opacity','1')
    await expect(page.locator('.ce-intro button')).toHaveCount(0)
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
    await page.screenshot({ path:info.outputPath(`landing-${width}.png`), fullPage:true })
    await page.reload()
    await expect(page.locator('.enter-intro-track')).toHaveCount(0)
    await page.getByTestId('for-recruiters').click()
    await page.goBack()
    await expect(page.locator('.enter-intro-track')).toHaveCount(0)
    expect(errors).toEqual([])
  })
}
test('Skip and keyboard focus release', async ({ page }) => {
  await page.goto('/')
  await page.getByRole('button', { name:'Skip intro' }).click()
  await expect(page.locator('.enter-intro-track')).toHaveCount(0)
  await expect(page.locator('#enter-home')).toBeFocused()
})
test('reduced motion and direct recruiter entry bypass motion', async ({ page }) => {
  await page.emulateMedia({ reducedMotion:'reduce' })
  await page.goto('/')
  await expect(page.locator('.enter-intro-track')).toHaveCount(0)
  await page.goto('/recruiter')
  await expect(page.locator('.auth-page')).toBeVisible()
})
test('runtime reduced motion releases intro', async ({ page }) => {
  await page.goto('/')
  await expect(page.locator('.enter-intro-track')).toBeVisible()
  await page.emulateMedia({ reducedMotion:'reduce' })
  await expect(page.locator('.enter-intro-track')).toHaveCount(0)
})
test('hidden page releases intro safely', async ({ page }) => {
  await page.goto('/')
  await expect(page.locator('.enter-intro-track')).toBeVisible()
  await page.evaluate(() => {
    Object.defineProperty(document,'hidden',{ configurable:true, value:true })
    document.dispatchEvent(new Event('visibilitychange'))
  })
  await expect(page.locator('.enter-intro-track')).toHaveCount(0)
})

for (const width of [390, 1440]) {
  test(`portal stage coverage and canvas cleanup at ${width}px`, async ({ page }, info) => {
    await page.setViewportSize({ width, height:900 })
    const clockStart = new Date('2026-01-01T00:00:00Z')
    await page.clock.install({ time: clockStart })
    await page.clock.pauseAt(clockStart)
    await page.goto('/?intro=replay')
    const start = Number(await page.locator('.enter-intro-shell').getAttribute('data-progress')) * 4400
    let elapsed = start
    for (const [name, time] of [['closed', 150], ['half-open', 1450], ['approach', 2800], ['white', 3720]] as const) {
      await page.clock.runFor(Math.max(0, time - elapsed))
      elapsed = Math.max(time, elapsed)
      await page.screenshot({ path:info.outputPath(`${name}-${width}.png`) })
    }
    await expect(page.locator('.enter-intro-wash')).toHaveCSS('opacity', '1')
    await page.clock.runFor(1000)
    await expect(page.locator('.enter-intro-bloom')).toHaveCount(0)
    await expect(page.locator('.enter-intro-track')).toHaveCount(0)
    await page.screenshot({ path:info.outputPath(`final-${width}.png`) })
  })
}

test('canvas unavailable still completes and candidate navigation remains usable', async ({ page }) => {
  await page.addInitScript(() => { HTMLCanvasElement.prototype.getContext = () => null })
  await page.goto('/')
  await expect(page.locator('.enter-intro-track')).toHaveCount(0, { timeout:6000 })
  await page.getByTestId('for-candidates').click()
  await expect(page.locator('.auth-page')).toBeVisible()
  await expect(page.locator('.enter-intro-track')).toHaveCount(0)
})
