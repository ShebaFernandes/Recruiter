import { expect, test } from '@playwright/test'

test('normal homepage has no company endorsement section or logo requests', async ({ page }) => {
  const requests: string[] = []
  page.on('request', request => requests.push(request.url()))
  await page.goto('/')
  await expect(page.locator('.ce-company-preview')).toHaveCount(0)
  await expect(page.getByRole('heading', { name: 'The best teams are built by ENTER.' })).toBeVisible()
  expect(requests.some(url => url.includes('-official.') || url.includes('CompanyLogoPreview'))).toBe(false)
})

for (const width of [1440, 1024, 390]) {
  test(`private company row at ${width}: hover, keyboard, motion and overflow`, async ({ page }, testInfo) => {
    await page.setViewportSize({ width, height: 900 })
    await page.emulateMedia({ reducedMotion: 'no-preference' })
    await page.goto('/?preview=company-logos')
    const section = page.locator('.ce-company-preview')
    const sequence = section.locator('.ce-company-sequence').first()
    await expect(section).toBeVisible()
    await section.scrollIntoViewIfNeeded()
    await section.locator('img').evaluateAll(images => Promise.all(images.map(i => (i as HTMLImageElement).decode())))
    await expect(page.getByRole('button', { name: /^About / })).toHaveCount(10)
    expect(await section.evaluate(e => e.previousElementSibling?.classList.contains('ce-mountain-hero'))).toBe(true)
    await page.mouse.move(0, 0)
    await expect(section).toHaveAttribute('data-paused', 'false')
    const matrix = () => sequence.evaluate(e => getComputedStyle(e).transform)
    const before = await matrix()
    await expect.poll(matrix).not.toBe(before)

    // Fast-forward CSS time to both sides of a loop: equivalent logo positions
    // must join without a gap or visible jump, regardless of responsive spacing.
    const seam = await section.evaluate(element => {
      const groups = [...element.querySelectorAll<HTMLElement>('.ce-company-sequence')]
      const animation = groups[0].getAnimations()[0]
      const duration = Number(animation.effect!.getTiming().duration)
      groups.forEach(g => g.getAnimations()[0].pause())
      groups.forEach(g => { g.getAnimations()[0].currentTime = duration - 1 })
      const end = groups[1].firstElementChild!.getBoundingClientRect().left
      groups.forEach(g => { g.getAnimations()[0].currentTime = duration })
      const start = groups[0].firstElementChild!.getBoundingClientRect().left
      groups.forEach(g => { g.getAnimations()[0].currentTime = 0; g.getAnimations()[0].play() })
      return Math.abs(start - end)
    })
    expect(seam).toBeLessThan(1)
    const logo = page.getByRole('button', { name: 'About Shiprocket', exact: true })
    await logo.hover()
    await expect(page.getByRole('tooltip')).toContainText('E-commerce logistics')
    await expect(sequence).toHaveCSS('animation-play-state', 'paused')
    const tooltip = await page.getByRole('tooltip').boundingBox()
    expect(tooltip!.x).toBeGreaterThanOrEqual(0)
    expect(tooltip!.x + tooltip!.width).toBeLessThanOrEqual(width)
    expect(await page.getByRole('tooltip').evaluate(e => e.parentElement === document.body)).toBe(true)
    await page.getByRole('tooltip').hover()
    await expect(page.getByRole('tooltip')).toBeVisible()
    await page.screenshot({ path: testInfo.outputPath(`company-preview-${width}.png`) })
    await page.mouse.move(0, 0)
    await expect(page.getByRole('tooltip')).toHaveCount(0)
    await page.getByRole('button', { name: 'Pause company logos' }).focus()
    await page.keyboard.press('Tab')
    await expect(logo).toBeFocused()
    await expect(page.getByRole('tooltip')).toContainText('Shiprocket')
    for (let i = 0; i < 9; i++) await page.keyboard.press('Tab')
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
}

test('mobile tap opens, switches and dismisses company details', async ({ browser }) => {
  const context = await browser.newContext({ viewport: { width: 390, height: 844 }, hasTouch: true, isMobile: true })
  const page = await context.newPage()
  await page.goto('/?preview=company-logos')
  await page.locator('.ce-company-preview').scrollIntoViewIfNeeded()
  const first = page.getByRole('button', { name: 'About Shiprocket' })
  await first.tap()
  await expect(page.getByRole('tooltip')).toContainText('Shiprocket')
  await first.tap()
  await expect(page.getByRole('tooltip')).toHaveCount(0)
  await first.tap()
  await page.getByRole('button', { name: 'About Bitscale AI' }).tap()
  await expect(page.getByRole('tooltip')).toContainText('Bitscale AI')
  await page.locator('.ce-company-toolbar p').tap()
  await expect(page.getByRole('tooltip')).toHaveCount(0)
  await context.close()
})
