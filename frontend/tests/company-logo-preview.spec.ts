import { expect, test } from '@playwright/test'

test.beforeEach(async ({ page }) => {
  await page.addInitScript(() => sessionStorage.setItem('enter-door-intro-seen', '1'))
})

test('normal homepage includes the approved logos without a preview flag', async ({ page }) => {
  await page.goto('/')
  await expect(page.getByRole('region', { name: 'Company logos', exact: true })).toBeVisible()
  await expect(page.getByRole('heading', { name: 'The best teams are built by ENTER.' })).toBeVisible()
  await page.locator('.ce-company-preview img').evaluateAll(images => Promise.all(images.map(image => (image as HTMLImageElement).decode())))
  await expect(page.getByRole('button', { name: 'About Shiprocket' })).toHaveCount(1)
  await expect(page.getByRole('button', { name: 'About WazirX' })).toHaveCount(1)
})

test('every added company is reachable by keyboard with readable details', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 900 })
  await page.goto('/')
  await page.getByRole('button', { name: 'Pause company logos' }).focus()
  const logos = page.getByRole('button', { name: /^About / })
  await expect(logos).toHaveCount(27)
  for (let index = 0; index < await logos.count(); index++) {
    await page.keyboard.press('Tab')
    const logo = logos.nth(index)
    await expect(logo).toBeFocused()
    await expect(logo).toBeInViewport()
    const name = (await logo.getAttribute('aria-label'))!.replace(/^About /, '')
    await expect(page.getByRole('tooltip')).toContainText(name)
    expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(390)
  }
  await expect(page.getByRole('button', { name: 'About MobiKwik' })).toHaveCount(0)
  await page.keyboard.press('Escape')
  await expect(page.getByRole('tooltip')).toHaveCount(0)
})

for (const width of [1440, 1024, 390]) {
  test(`public company row at ${width}: hover, keyboard, motion and overflow`, async ({ page }, testInfo) => {
    await page.setViewportSize({ width, height: 900 })
    await page.emulateMedia({ reducedMotion: 'no-preference' })
    await page.goto('/')
    const section = page.locator('.ce-company-preview')
    const sequence = section.locator('.ce-company-sequence').first()
    await expect(section).toBeVisible()
    // Logos must sit comfortably inside the initial 900px viewport, not at
    // its bottom edge; the headline/description remain above the logo row.
    const initialLayout = await page.evaluate(() => ({
      logoTop: document.querySelector('.ce-company-preview img')!.getBoundingClientRect().top,
      copyBottom: document.querySelector('.ce-intro-aside')!.getBoundingClientRect().bottom,
    }))
    expect(initialLayout.logoTop).toBeLessThan(width > 760 ? 810 : 720)
    expect(initialLayout.copyBottom).toBeLessThan(initialLayout.logoTop - 150)
    await expect(page.locator('.ce-entry-section')).toHaveCount(0)
    await expect(page.getByText(/The impact we create extends/)).toHaveCount(0)
    await expect(page.locator('footer')).toHaveCount(0)
    expect(await page.evaluate(() => document.documentElement.scrollHeight)).toBeLessThanOrEqual(900)
    await section.scrollIntoViewIfNeeded()
    await section.locator('img').evaluateAll(images => Promise.all(images.map(i => (i as HTMLImageElement).decode())))
    await expect(page.getByRole('button', { name: /^About / })).toHaveCount(27)
    await expect(section.locator('img').first()).toHaveCSS('filter', 'grayscale(1)')
    expect(await section.evaluate(e => e.previousElementSibling?.classList.contains('ce-mountain-hero'))).toBe(true)
    const spacing = await section.evaluate(element => {
      const hero = element.previousElementSibling!.getBoundingClientRect()
      const logo = element.querySelector('img')!.getBoundingClientRect()
      return { gap: logo.top - hero.bottom, height: element.getBoundingClientRect().height }
    })
    expect(spacing.gap).toBeGreaterThan(20)
    expect(spacing.gap).toBeLessThan(48)
    expect(spacing.height).toBe(113)
    await expect(section.getByText(/public logo permissions pending/)).toHaveCount(0)
    const pause = page.getByRole('button', { name: 'Pause company logos' })
    await expect(pause).toHaveCSS('clip-path', 'inset(50%)')
    await page.mouse.move(0, 0)
    await expect(section).toHaveAttribute('data-paused', 'false')
    const matrix = () => sequence.evaluate(e => getComputedStyle(e).transform)
    const before = await matrix()
    await expect.poll(matrix).not.toBe(before)

    const logo = page.getByRole('button', { name: 'About Shiprocket', exact: true })
    // Pause at the strip edge like a real pointer entering it, then use a
    // visible copy. The first original may have already travelled offscreen
    // on a slower run; this must not assume a particular animation time.
    const strip = await section.boundingBox()
    await page.mouse.move(width / 2, strip!.y + 2)
    await expect(sequence).toHaveCSS('animation-play-state', 'paused')
    const logoPoint = await section.locator('.ce-company-logo:has(img[src*="shiprocket"])').evaluateAll(elements => {
      const visible = elements.map(e => e.getBoundingClientRect())
        .find(r => Math.min(r.right, innerWidth) - Math.max(r.left, 0) > 30)
      return visible ? { x: (Math.max(visible.left, 0) + Math.min(visible.right, innerWidth)) / 2, y: visible.top + visible.height / 2 } : null
    })
    expect(logoPoint).not.toBeNull()
    await page.mouse.move(logoPoint!.x, logoPoint!.y)
    await expect(page.getByRole('tooltip')).toContainText('E-commerce logistics')
    await expect(sequence).toHaveCSS('animation-play-state', 'paused')
    const stopped = await matrix()
    await page.waitForTimeout(180)
    expect(await matrix()).toBe(stopped)
    const tooltip = await page.getByRole('tooltip').boundingBox()
    expect(tooltip!.x).toBeGreaterThanOrEqual(0)
    expect(tooltip!.x + tooltip!.width).toBeLessThanOrEqual(width)
    expect(await page.getByRole('tooltip').evaluate(e => e.parentElement === document.body)).toBe(true)
    await page.getByRole('tooltip').hover()
    await expect(page.getByRole('tooltip')).toBeVisible()
    await page.screenshot({ path: testInfo.outputPath(`company-preview-${width}.png`) })
    await page.mouse.move(0, 0)
    await expect(page.getByRole('tooltip')).toHaveCount(0)
    await pause.focus()
    await expect(pause).toHaveCSS('clip-path', 'none')
    await page.keyboard.press('Enter')
    await expect(page.getByRole('button', { name: 'Resume company logos' })).toHaveAttribute('aria-pressed', 'true')
    await page.keyboard.press('Enter')
    await page.keyboard.press('Tab')
    await expect(logo).toBeFocused()
    await expect(page.getByRole('tooltip')).toContainText('Shiprocket')
    await page.keyboard.press('Tab')
    await expect(page.getByRole('button', { name: 'About WazirX' })).toBeFocused()
    await expect(page.getByRole('button', { name: 'About WazirX' })).toBeInViewport()
    await expect(page.getByRole('tooltip')).toContainText('WazirX')
    await page.keyboard.press('Escape')
    await expect(page.getByRole('tooltip')).toHaveCount(0)
    expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(width)
    await page.emulateMedia({ reducedMotion: 'reduce' })
    await expect(sequence).toHaveCSS('animation-name', 'none')
    await expect(section.locator('[data-duplicate="true"]')).toBeHidden()
    await expect(section.locator('.ce-company-window')).toHaveCSS('overflow-x', 'auto')
  })

  test(`company loop joins seamlessly at ${width}px`, async ({ page }) => {
    await page.setViewportSize({ width, height: 900 })
    await page.emulateMedia({ reducedMotion: 'no-preference' })
    await page.goto('/')
    const section = page.locator('.ce-company-preview')
    await section.scrollIntoViewIfNeeded()
    // Isolate time-seeking from interaction tests: WAAPI play/pause overrides
    // CSS play-state, so it must not be reused to test normal hover pausing.
    const seam = await section.evaluate(element => {
      const groups = [...element.querySelectorAll<HTMLElement>('.ce-company-sequence')]
      const duration = Number(groups[0].getAnimations()[0].effect!.getTiming().duration)
      groups.forEach(g => g.getAnimations()[0].pause())
      groups.forEach(g => { g.getAnimations()[0].currentTime = duration - 1 })
      const end = groups[1].firstElementChild!.getBoundingClientRect().left
      groups.forEach(g => { g.getAnimations()[0].currentTime = duration })
      const start = groups[0].firstElementChild!.getBoundingClientRect().left
      return Math.abs(start - end)
    })
    expect(seam).toBeLessThan(1)
  })
}

test('mobile tap opens, switches and dismisses company details', async ({ browser }) => {
  const context = await browser.newContext({ viewport: { width: 390, height: 844 }, hasTouch: true, isMobile: true })
  await context.addInitScript(() => sessionStorage.setItem('enter-door-intro-seen', '1'))
  const page = await context.newPage()
  await page.goto('/')
  await page.locator('.ce-company-preview').scrollIntoViewIfNeeded()
  const first = page.getByRole('button', { name: 'About Shiprocket' })
  const tapMovingLogo = async (name: string) => {
    const bounds = await page.getByRole('button', { name, exact: true }).boundingBox()
    await page.touchscreen.tap(bounds!.x + bounds!.width / 2, bounds!.y + bounds!.height / 2)
  }
  await tapMovingLogo('About Shiprocket')
  await expect(page.getByRole('tooltip')).toContainText('Shiprocket')
  await first.tap()
  await expect(page.getByRole('tooltip')).toHaveCount(0)
  await tapMovingLogo('About Shiprocket')
  await tapMovingLogo('About WazirX')
  await expect(page.getByRole('tooltip')).toContainText('WazirX')
  await page.locator('.ce-intro h1').tap()
  await expect(page.getByRole('tooltip')).toHaveCount(0)
  await context.close()
})
