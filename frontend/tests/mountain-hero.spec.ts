import { expect, test } from '@playwright/test'

for (const width of [1440, 1024, 390]) {
  test(`mountain hero at ${width}px: aligned layers, bounded motion, navigation`, async ({ page }, testInfo) => {
    await page.setViewportSize({ width, height: 900 })
    await page.emulateMedia({ reducedMotion: 'no-preference' })
    await page.goto('/')
    await page.evaluate(() => document.fonts.ready)
    const hero = page.locator('.ce-mountain-hero')
    const scene = page.locator('.ce-mountain-scene')
    const layers = scene.locator('img')
    await expect(layers).toHaveCount(6)
    await expect(scene).toHaveAttribute('aria-hidden', 'true')
    await expect(scene).toHaveCSS('pointer-events', 'none')
    await expect(scene).toHaveAttribute('data-active', 'true')
    await layers.evaluateAll(images => Promise.all(images.map(image => (image as HTMLImageElement).decode())))
    expect(await layers.evaluateAll(images => images.every(image => {
      const img = image as HTMLImageElement
      return img.naturalWidth === 1536 && img.naturalHeight === 1024 && img.alt === ''
    }))).toBe(true)
    const dimensions = await layers.evaluateAll(images => images.map(image => [image.clientWidth, image.clientHeight]))
    expect(dimensions.every(size => size.toString() === dimensions[0].toString())).toBe(true)
    await expect(page.getByRole('heading', { name: 'A career is more than a job title.' })).toBeVisible()
    expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(width)
    await page.screenshot({ path: testInfo.outputPath(`mountain-hero-${width}.png`), fullPage: true, animations: 'disabled' })
    const stableHeight = await hero.evaluate(element => element.getBoundingClientRect().height)
    await page.evaluate(() => window.scrollTo(0, 250))
    const offset = (depth: string) => scene.evaluate((element, name) => parseFloat((element as HTMLElement).style.getPropertyValue(`--ce-${name}-offset`) || '0'), depth)
    if (width > 760) {
      await expect.poll(() => offset('foreground')).toBeGreaterThan(0)
      expect(await offset('foreground')).toBeGreaterThan(await offset('middle'))
      expect(await offset('middle')).toBeGreaterThan(await offset('distant'))
      expect(await offset('foreground')).toBeGreaterThan(20)
      expect(await offset('foreground')).toBeLessThanOrEqual(stableHeight * 0.045)
    } else {
      expect(await offset('foreground')).toBe(0)
      await expect(scene.locator('.ce-landscape-foreground')).toHaveCSS('transform', 'none')
    }
    await expect(scene.locator('.ce-landscape-sky')).toHaveCSS('transform', 'none')
    expect(await hero.evaluate(element => element.getBoundingClientRect().height)).toBe(stableHeight)
    // Cloud reversal endpoints must retain overscan on both sides of the hero.
    for (const progress of [0, 0.5, 1, 1.5, 2]) {
      await scene.locator('.ce-landscape-clouds-front, .ce-landscape-clouds-back').evaluateAll((images, t) => {
        images.forEach(image => image.getAnimations().forEach(animation => {
          const timing = animation.effect!.getTiming()
          animation.pause()
          animation.currentTime = Number(timing.duration) * t + timing.delay
        }))
      }, progress)
      const coverage = await scene.locator('img').evaluateAll(images => images.every(image => {
        const bounds = image.getBoundingClientRect()
        const viewport = image.closest('.ce-mountain-scene')!.getBoundingClientRect()
        return bounds.left <= viewport.left && bounds.right >= viewport.right && bounds.top <= viewport.top && bounds.bottom >= viewport.bottom
      }))
      expect(coverage).toBe(true)
    }
    // The compact lower sections are shorter than a 900px desktop viewport.
    // Use a short window to move the hero entirely offscreen, not merely partway.
    await page.setViewportSize({ width, height: 500 })
    await page.evaluate(() => window.scrollTo(0, document.body.scrollHeight))
    expect(await hero.evaluate(element => element.getBoundingClientRect().bottom)).toBeLessThanOrEqual(0)
    await expect(scene).toHaveAttribute('data-active', 'false')
    await expect(scene.locator('.ce-landscape-clouds-back')).toHaveCSS('animation-play-state', 'paused')
    await page.getByRole('navigation', { name: 'Main navigation' }).getByRole('link', { name: 'For recruiters' }).click()
    await expect(page.locator('#recruiter-entry')).toBeInViewport()
    await page.getByTestId('for-recruiters').click()
    await expect(page.getByLabel('Company')).toBeVisible()
  })
}

test('reduced motion and mobile resizing remove parallax immediately', async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 900 })
  await page.emulateMedia({ reducedMotion: 'no-preference' })
  await page.goto('/')
  const scene = page.locator('.ce-mountain-scene')
  await expect(scene).toHaveAttribute('data-active', 'true')
  await page.evaluate(() => window.scrollTo(0, 200))
  await expect.poll(() => scene.evaluate(e => e.style.getPropertyValue('--ce-foreground-offset'))).not.toBe('0px')
  await page.emulateMedia({ reducedMotion: 'reduce' })
  await expect(scene).toHaveAttribute('data-active', 'false')
  await expect(scene.locator('.ce-landscape-clouds-front')).toHaveCSS('animation-name', 'none')
  await expect(scene.locator('.ce-landscape-foreground')).toHaveCSS('transform', 'none')
  await expect.poll(() => scene.evaluate(e => e.style.getPropertyValue('--ce-foreground-offset'))).toBe('0px')
  await page.emulateMedia({ reducedMotion: 'no-preference' })
  await page.setViewportSize({ width: 390, height: 844 })
  await expect(scene.locator('.ce-landscape-foreground')).toHaveCSS('transform', 'none')
  await expect.poll(() => scene.evaluate(e => e.style.getPropertyValue('--ce-foreground-offset'))).toBe('0px')
})

for (const width of [1440, 390]) {
  test(`clouds visibly move within seconds at ${width}px without moving content`, async ({ page }) => {
    await page.setViewportSize({ width, height: 900 })
    await page.emulateMedia({ reducedMotion: 'no-preference' })
    await page.goto('/')
    await page.evaluate(() => document.fonts.ready)
    const scene = page.locator('.ce-mountain-scene')
    await expect(scene).toHaveAttribute('data-active', 'true')
    await scene.locator('img').evaluateAll(images => Promise.all(images.map(image => (image as HTMLImageElement).decode())))
    const movement = await scene.evaluate(async element => {
      const front = element.querySelector('.ce-landscape-clouds-front')!
      const back = element.querySelector('.ce-landscape-clouds-back')!
      const heading = document.querySelector('.ce-intro h1') as HTMLElement
      const read = () => ({
        front: new DOMMatrixReadOnly(getComputedStyle(front).transform).m41,
        back: new DOMMatrixReadOnly(getComputedStyle(back).transform).m41,
        heading: [heading.offsetTop, heading.offsetLeft, heading.offsetWidth, heading.offsetHeight],
      })
      const before = read()
      // Observe real browser animation time; do not seek or simulate progress.
      await new Promise(resolve => setTimeout(resolve, 2200))
      return { before, after: read() }
    })
    const frontDelta = movement.after.front - movement.before.front
    const backDelta = movement.after.back - movement.before.back
    expect(Math.abs(frontDelta)).toBeGreaterThan(width > 760 ? 8 : 1)
    expect(Math.abs(backDelta)).toBeGreaterThan(width > 760 ? 5 : 0.5)
    expect(frontDelta * backDelta).toBeLessThan(0)
    expect(movement.after.heading).toEqual(movement.before.heading)
    await page.emulateMedia({ reducedMotion: 'reduce' })
    await expect(scene.locator('.ce-landscape-clouds-front')).toHaveCSS('transform', 'none')
    await expect(scene.locator('.ce-landscape-clouds-back')).toHaveCSS('transform', 'none')
  })
}

test('delayed artwork cannot move the content or entry sections', async ({ page }) => {
  await page.emulateMedia({ reducedMotion: 'reduce' })
  let release!: () => void
  const gate = new Promise<void>(resolve => { release = resolve })
  await page.route('**/hero/mountain-v1/*.webp', async route => { await gate; await route.continue() })
  await page.goto('/', { waitUntil: 'domcontentloaded' })
  await page.evaluate(() => document.fonts.ready)
  const bounds = () => page.locator('.ce-mountain-hero, .ce-intro h1, .ce-entry-section').evaluateAll(elements => elements.map(element => {
    const { x, y, width, height } = element.getBoundingClientRect()
    return { x, y, width, height }
  }))
  const before = await bounds()
  release()
  await page.locator('.ce-landscape-layer').evaluateAll(images => Promise.all(images.map(image => (image as HTMLImageElement).decode())))
  expect(await bounds()).toEqual(before)
})
