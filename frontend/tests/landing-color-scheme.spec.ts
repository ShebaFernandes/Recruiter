import { devices, expect, test } from '@playwright/test'

test.use({ ...devices['Pixel 7'], deviceScaleFactor: 1, reducedMotion: 'reduce' })

for (const width of [360, 390, 430]) {
  test(`landing artwork and text stay identical in light, dark and automatic darkening at ${width}px`, async ({ page, context }, info) => {
    await page.setViewportSize({ width, height: 844 })
    await page.addInitScript(() => sessionStorage.setItem('enter-door-intro-seen', '1'))
    await page.route('**/api/v1/auth/me/', route => route.fulfill({ status: 401, json: {} }))
    // Production CSP blocks remote fonts; use the same fallback for this comparison.
    await page.route('https://fonts.googleapis.com/**', route => route.abort())
    await page.emulateMedia({ colorScheme: 'light' })
    await page.goto('/')
    await page.evaluate(() => document.fonts.ready)
    await page.locator('img').evaluateAll(async images => {
      await Promise.all(images.map(image => (image as HTMLImageElement).decode()))
    })
    const session = await context.newCDPSession(page)
    let light: Buffer | undefined
    for (const mode of ['light', 'dark', 'auto-dark'] as const) {
      await page.emulateMedia({ colorScheme: mode === 'light' ? 'light' : 'dark' })
      await session.send('Emulation.setAutoDarkModeOverride', { enabled: mode === 'auto-dark' })
      await page.evaluate(() => new Promise<void>(resolve => requestAnimationFrame(() => requestAnimationFrame(() => resolve()))))
      await expect(page.locator('.ce-intro h1')).toHaveCSS('color', 'rgb(11, 31, 58)')
      await expect(page.getByTestId('for-candidates')).toHaveCSS('color', 'rgb(11, 31, 58)')
      await expect(page.locator('.ce-logo img')).toBeVisible()
      await expect(page.locator('.ce-headline-wordmark')).toBeVisible()
      await expect(page.locator('.landing-background img')).toHaveCount(6)
      const capture = await page.screenshot({ path: info.outputPath(`${mode}-${width}.png`), animations: 'disabled' })
      if (mode === 'light') light = capture
      else expect(capture.equals(light!), `${mode} must preserve every rendered pixel, including logo and mountains`).toBe(true)
    }
    await session.detach()
  })
}
