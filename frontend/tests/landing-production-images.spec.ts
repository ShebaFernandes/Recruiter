import { expect, test } from '@playwright/test'
import { writeFile } from 'node:fs/promises'

// Only the isolated production-build static server is used; no candidate backend writes.
for (const width of [390, 768, 1440]) for (const throttled of [false, true]) {
  test(`landing artwork at ${width}px ${throttled ? 'slow-mobile' : 'normal'}`, async ({ page }, info) => {
    test.setTimeout(120_000)
    await page.setViewportSize({ width, height: 900 })
    const errors: string[] = []
    const failedImages: string[] = []
    const consoleErrors: string[] = []
    page.on('console', message => { if (message.type() === 'error') consoleErrors.push(message.text()) })
    page.on('pageerror', error => errors.push(error.message))
    page.on('response', response => {
      if (response.request().resourceType() === 'image' && response.status() >= 400) failedImages.push(response.url())
    })
    page.on('requestfailed', request => {
      if (request.resourceType() === 'image') failedImages.push(request.url())
    })
    if (throttled) {
      const network = await page.context().newCDPSession(page)
      await network.send('Network.enable')
      await network.send('Network.emulateNetworkConditions', {
        offline: false, latency: 150, downloadThroughput: 200_000,
        uploadThroughput: 75_000, connectionType: 'cellular3g',
      })
    }
    await page.goto('/')
    await expect(page.locator('#ce-title')).toBeVisible()
    await page.evaluate(() => document.fonts.ready)
    // Native image loading must not compete with the headline using high priority.
    await expect(page.locator('.landing-background img')).toHaveCount(6)
    for (const image of await page.locator('.landing-background img').all()) {
      await expect(image).toHaveAttribute('loading', 'eager')
      await expect(image).toHaveAttribute('fetchpriority', 'low')
      await expect.poll(() => image.evaluate(el => (el as HTMLImageElement).currentSrc)).toMatch(/-(1440|1536)-/)
      await image.evaluate(image => (image as HTMLImageElement).decode())
    }
    await page.screenshot({ path: info.outputPath(`hero-${width}.png`), animations: 'disabled' })
    const sections = [
      ['founding', '.growth-stages__grid .growth-stage-card--founding'],
      ['leadership', '.growth-stages__grid .growth-stage-card--leadership'],
      ['closing', '.closing-cta'],
    ] as const
    const images = []
    for (const [name, selector] of sections) {
      const section = page.locator(selector)
      await section.scrollIntoViewIfNeeded()
      const image = section.locator('img').first()
      await expect.poll(() => image.evaluate(image => (image as HTMLImageElement).currentSrc))
        .toContain('/assets/')
      await image.evaluate(image => (image as HTMLImageElement).decode())
      await expect(section.locator('source').first()).toHaveCSS('display', 'none')
      await expect(image).toBeVisible()
      expect(await image.evaluate(image => (image as HTMLImageElement).naturalWidth)).toBeGreaterThan(0)
      images.push(await image.evaluate(image => ({
        source: (image as HTMLImageElement).currentSrc,
        width: image.getAttribute('width'), height: image.getAttribute('height'),
        opacity: getComputedStyle(image).opacity, visibility: getComputedStyle(image).visibility,
      })))
      await section.screenshot({ path: info.outputPath(`${name}-${width}.png`), animations: 'disabled' })
    }
    // Walk every chapter so all deferred CSS artwork and logos are exercised too.
    for (const section of await page.locator('.simple-landing > section, .evidence-to-hires').all()) {
      await section.scrollIntoViewIfNeeded()
    }
    expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(width)
    expect(failedImages).toEqual([])
    expect(errors).toEqual([])
    expect(consoleErrors.filter(message => !message.includes('401 (Unauthorized)'))).toEqual([])
    await writeFile(info.outputPath('image-verification.json'), JSON.stringify({ images, failedImages, errors, consoleErrors }, null, 2))
    await info.attach('rendered-images', { body: JSON.stringify(images, null, 2), contentType: 'application/json' })
  })
}

test('reduced motion keeps all three landscapes visible', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 900 })
  await page.emulateMedia({ reducedMotion: 'reduce' })
  await page.goto('/')
  for (const selector of ['.growth-stage-card--founding', '.growth-stage-card--leadership', '.closing-cta']) {
    const section = page.locator(selector)
    await section.scrollIntoViewIfNeeded()
    const image = section.locator('img').first()
    await expect.poll(() => image.evaluate(el => (el as HTMLImageElement).currentSrc)).toContain('/assets/')
    await image.evaluate(el => (el as HTMLImageElement).decode())
    await expect(image).toBeVisible()
  }
  for (const layer of await page.locator('.landing-background img').all()) {
    await expect(layer).toHaveCSS('animation-name', 'none')
  }
})

test('closing landscape recovers when both optimized formats fail', async ({ page }) => {
  await page.route(/\/assets\/closing-[^/]+\.(avif|webp)$/, route => route.abort())
  await page.goto('/')
  const banner = page.locator('.closing-cta')
  await banner.scrollIntoViewIfNeeded()
  const image = banner.locator('img').first()
  await expect.poll(() => image.evaluate(el => (el as HTMLImageElement).currentSrc))
    .toContain('/media/section10-closing-mountain-lush.png')
  await image.evaluate(el => (el as HTMLImageElement).decode())
  await expect(image).toBeVisible()
  expect(await image.evaluate(el => (el as HTMLImageElement).naturalWidth)).toBeGreaterThan(1000)
})

test('high density mobile selects enough detail for the tall banner crop', async ({ browser }) => {
  const context = await browser.newContext({
    viewport: { width: 390, height: 900 }, deviceScaleFactor: 3, isMobile: true, hasTouch: true,
  })
  const page = await context.newPage()
  await page.goto('/')
  const banner = page.locator('.closing-cta')
  await banner.scrollIntoViewIfNeeded()
  const image = banner.locator('img').first()
  await expect.poll(() => image.evaluate(el => (el as HTMLImageElement).currentSrc))
    .toContain('/assets/closing-1983-')
  await image.evaluate(el => (el as HTMLImageElement).decode())
  await expect(image).toBeVisible()
  await context.close()
})
