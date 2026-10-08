import { expect, test, type Page } from '@playwright/test'
import { pathToFileURL } from 'node:url'

async function enterWorkspace(page: Page) {
  await page.goto('/')
  await page.getByTestId('for-recruiters').click()
  await page.getByLabel('Full name').fill('Riya Sen')
  await page.getByLabel('Company').fill('Search UI Verification')
  await page.getByLabel('Email').fill(`search-ui-${Date.now()}@example.com`)
  await page.getByLabel('Password').fill('Search-ui-password-123!')
  await page.getByRole('button', { name: 'Create account' }).click()
  await expect(page.getByRole('heading', { name: 'Who are we hiring today?' })).toBeVisible()
}

for (const width of [1440, 1024, 390]) {
  test(`real recruiter search and clarification at ${width}px`, async ({ page }, info) => {
    await page.setViewportSize({ width, height: 960 })
    await enterWorkspace(page)
    const composer = page.getByLabel('Candidate search', { exact: true })
    await expect(page.getByRole('button', { name: 'Search talent' })).toBeDisabled()
    const longQuery = 'Backend engineers with experience building reliable distributed services and production APIs. '.repeat(5)
    await composer.fill(longQuery)
    await expect(composer).toHaveValue(longQuery)
    await expect(composer).toHaveAttribute('type', 'text')
    expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(width)
    if (width >= 1024) {
      const bar = await page.locator('.chat-composer').boundingBox()
      expect(bar?.width).toBe(680)
      expect(bar?.height).toBe(58)
      await expect(page.getByRole('heading', { name: 'Who are we hiring today?' })).toHaveCSS('font-size', '24px')
    }
    await page.getByRole('button', { name: 'Production ML engineers', exact: true }).click()
    await expect(composer).toBeFocused()
    await expect(composer).toHaveValue('Production machine learning engineers with 4 years experience, remote okay')
    await composer.press('End')
    await page.evaluate(() => document.fonts.ready)
    await page.screenshot({ path: info.outputPath(`search-${width}.png`), fullPage: true, animations: 'disabled' })

    await page.getByRole('button', { name: 'Projects', exact: true }).click()
    const panel = page.getByRole('complementary', { name: 'Projects', exact: true })
    await expect(panel).toBeVisible()
    const mainBox = await page.locator('.editorial-search').boundingBox()
    const panelBox = await panel.boundingBox()
    expect(mainBox && panelBox && (panelBox.x >= mainBox.x + mainBox.width || panelBox.y >= mainBox.y + mainBox.height)).toBeTruthy()
    await page.getByLabel('New project name').fill(`Search design ${width}`)
    await page.getByRole('button', { name: 'Create project' }).click()
    await expect(panel.getByText(`Search design ${width}`, { exact: true })).toBeVisible()
    await page.getByRole('button', { name: 'Close workspace panel' }).click()
    await expect(page.getByText(`Search design ${width}`, { exact: true })).toBeVisible()
    await page.getByRole('button', { name: 'New search', exact: true }).click()
    await expect(composer).toHaveValue('')
    await composer.fill('Backend engineer with 4 years experience')
    const response = page.waitForResponse(response => /\/searches\/$/.test(response.url()) && response.request().method() === 'POST')
    await composer.press('Enter')
    const created = await response
    expect(created.ok()).toBeTruthy()
    const search = await created.json()
    expect(search.state).toBe('needs_clarification')
    expect(search.criteria).toHaveProperty('min_experience', 4)
    await expect(page.getByText('One detail before I search')).toBeVisible()
    await expect(page.getByText(/preferred location/)).toBeVisible()
    await page.getByRole('button', { name: 'Let me type it', exact: true }).click()
    await expect(page.getByLabel('Clarification answer')).toBeFocused()
    await page.getByLabel('Clarification answer').fill('Bengaluru')
    await page.getByLabel('Clarification answer').press('Tab')
    await expect(page.getByRole('button', { name: 'Continue', exact: true })).toBeFocused()
    expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(width)
    await page.evaluate(() => window.scrollTo(0, 0))
    await page.screenshot({ path: info.outputPath(`clarification-${width}.png`), fullPage: true, animations: 'disabled' })
    await page.getByRole('button', { name: 'Recent searches', exact: true }).click()
    await page.locator('.workspace-list').getByRole('button').filter({ hasText: 'Backend engineer with 4 years experience' }).click()
    await expect(page.getByText('One detail before I search')).toBeVisible()
    await page.getByRole('button', { name: 'Bengaluru', exact: true }).click()
    await expect(page.locator('.results-view')).toBeVisible()
    await expect(page.locator('.recruiter-search-mode')).toHaveCount(0)
    await expect(page.getByRole('button', { name: 'Refine', exact: true })).toBeVisible()
    await page.getByRole('button', { name: 'New search', exact: true }).click()
    await page.getByRole('button', { name: 'Candidate updates', exact: true }).click()
    await expect(page.getByRole('complementary', { name: 'Candidate updates', exact: true })).toBeVisible()
    await page.getByRole('button', { name: 'Close workspace panel' }).click()
    expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(width)
  })
}

test('search keyboard controls and reduced-motion settings remain usable', async ({ page }) => {
  await page.emulateMedia({ reducedMotion: 'reduce' })
  await enterWorkspace(page)
  await page.getByLabel('Candidate search', { exact: true }).fill('Backend engineer with 4 years experience')
  await page.getByLabel('Candidate search', { exact: true }).focus()
  await page.keyboard.press('Tab')
  await expect(page.getByRole('button', { name: 'Search by voice' })).toBeFocused()
  await page.keyboard.press('Tab')
  const submit = page.getByRole('button', { name: 'Search talent' })
  await expect(submit).toBeFocused()
  await expect(submit).toHaveCSS('outline-style', 'solid')
  await submit.press('Enter')
  await expect(page.locator('.enter-message')).toBeVisible()
  await expect(page.locator('.enter-message')).toHaveCSS('animation-name', 'none')
  await page.getByLabel('Clarification answer').fill('Bengaluru')
  await page.getByRole('button', { name: 'Continue', exact: true }).click()
  await expect(page.locator('.results-view')).toBeVisible()
})

test('desktop search proportions match the supplied original HTML', async ({ page, context }, info) => {
  const mockupPath = process.env.ENTER_MOCKUP_PATH
  test.skip(!mockupPath, 'Set ENTER_MOCKUP_PATH to compare against the external original HTML.')
  const reference = await context.newPage()
  await reference.setViewportSize({ width: 1440, height: 960 })
  await reference.goto(pathToFileURL(mockupPath!).href)
  // Select the static reference screen, without invoking its demo authentication/data.
  await reference.evaluate(() => {
    document.querySelectorAll('.screen').forEach(element => element.classList.remove('active'))
    document.querySelector('#home')?.classList.add('active')
    document.body.classList.add('home-shell-active')
  })
  await reference.evaluate(() => document.fonts.ready)
  await reference.screenshot({ path: info.outputPath('original-1440.png'), animations: 'disabled' })
  await page.setViewportSize({ width: 1440, height: 960 })
  await enterWorkspace(page)
  await page.evaluate(() => document.fonts.ready)
  await page.screenshot({ path: info.outputPath('corrected-1440.png'), animations: 'disabled' })
  const measure = async (target: Page, selectors: string[]) => Promise.all(selectors.map(selector =>
    target.locator(selector).first().evaluate(element => {
      const box = element.getBoundingClientRect()
      const css = getComputedStyle(element)
      return { width: box.width, height: box.height, y: box.y, bottom: box.bottom,
        fontSize: css.fontSize, fontFamily: css.fontFamily, borderRadius: css.borderRadius }
    })))
  const original = await measure(reference, ['.home-hero h1', '.searchbar', '#searchBtn', '.search-prompt-tabs button'])
  const current = await measure(page, ['.editorial-search h1', '.chat-composer', '.search-enter-button', '.search-hints button'])
  for (const index of [1, 2]) {
    expect(current[index].width).toBeCloseTo(original[index].width, 0)
    expect(current[index].height).toBeCloseTo(original[index].height, 0)
    expect(current[index].borderRadius).toBe(original[index].borderRadius)
  }
  for (const index of [0, 3]) {
    expect(current[index].fontSize).toBe(original[index].fontSize)
    expect(current[index].fontFamily).toBe(original[index].fontFamily)
    expect(current[index].height).toBeCloseTo(original[index].height, 0)
  }
  expect(current[1].y - current[0].bottom).toBeCloseTo(original[1].y - original[0].bottom, 0)
  expect(current[3].y - current[1].bottom).toBeCloseTo(original[3].y - original[1].bottom, 0)
  await reference.close()
})
