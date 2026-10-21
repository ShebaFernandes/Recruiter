import { expect, type Locator, type Page } from '@playwright/test'

export const enterColors = {
  bg: 'rgb(247, 249, 252)', surface: 'rgb(255, 255, 255)', text: 'rgb(48, 56, 66)',
  muted: 'rgb(98, 105, 113)', primary: 'rgb(48, 56, 66)', hover: 'rgb(36, 43, 51)',
  soft: 'rgb(247, 249, 252)', border: 'rgb(214, 223, 234)',
}
export const candidateColors = {
  ...enterColors,
}

export async function expectEnterPage(page: Page, surface: Locator, colors = enterColors) {
  await expect(surface).toHaveCSS('background-color', 'rgba(0, 0, 0, 0)')
  await expect(page.locator('.platform-background')).toHaveCount(1)
  await expect(page.locator('.platform-background')).toHaveCSS('position', 'fixed')
  await expect(surface).toHaveCSS('color', colors.text)
  await expect(surface).toHaveCSS('font-family', /DM Sans/)
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true)
}

export async function expectEnterPrimary(button: Locator, colors = enterColors) {
  await expect(button).toHaveCSS('background-color', colors.primary)
  await expect(button).toHaveCSS('color', colors.surface)
  await expect(button).toHaveCSS('border-radius', '6px')
  await expect(button).toHaveCSS('font-family', /DM Sans/)
}

export async function expectEnterField(field: Locator, colors = enterColors) {
  await expect(field).toHaveCSS('background-color', 'rgba(255, 255, 255, 0.98)')
  await expect(field).toHaveCSS('border-radius', '6px')
  await expect(field).toHaveCSS('font-family', /DM Sans/)
  await field.focus()
  // All form controls have either the shared focus halo or the keyboard outline.
  await expect.poll(() => field.evaluate((el, primary) => {
    const s = getComputedStyle(el)
    return s.outlineStyle === 'solid' && s.outlineColor === primary || s.boxShadow === 'rgba(22, 59, 101, 0.16) 0px 0px 0px 3px'
  }, colors.primary)).toBe(true)
}

export async function expectEnterCard(card: Locator, kind: 'auth' | 'result' = 'result') {
  // Approved near-solid ivory hierarchy; dense results are more opaque than auth.
  await expect(card).toHaveCSS('background-color', kind === 'auth' ? 'rgba(250, 248, 244, 0.94)' : 'rgba(250, 248, 244, 0.96)')
  await expect(card).toHaveCSS('border-color', kind === 'auth' ? 'rgba(255, 255, 255, 0.38)' : 'rgba(255, 255, 255, 0.42)')
  await expect(card).toHaveCSS('border-radius', kind === 'auth' ? '16px' : '10px')
}
