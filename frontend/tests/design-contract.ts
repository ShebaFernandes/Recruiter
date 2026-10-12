import { expect, type Locator, type Page } from '@playwright/test'

export const enterColors = {
  bg: 'rgb(250, 249, 246)', surface: 'rgb(255, 255, 255)', text: 'rgb(25, 21, 43)',
  muted: 'rgb(110, 105, 123)', primary: 'rgb(109, 74, 255)', hover: 'rgb(87, 55, 217)',
  soft: 'rgb(240, 236, 255)', border: 'rgb(230, 226, 235)',
}

export async function expectEnterPage(page: Page, surface: Locator) {
  await expect(surface).toHaveCSS('background-color', enterColors.bg)
  await expect(surface).toHaveCSS('color', enterColors.text)
  await expect(surface).toHaveCSS('font-family', /DM Sans/)
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true)
}

export async function expectEnterPrimary(button: Locator) {
  await expect(button).toHaveCSS('background-color', enterColors.primary)
  await expect(button).toHaveCSS('color', enterColors.surface)
  await expect(button).toHaveCSS('border-radius', '6px')
  await expect(button).toHaveCSS('font-family', /DM Sans/)
}

export async function expectEnterField(field: Locator) {
  await expect(field).toHaveCSS('background-color', enterColors.surface)
  await expect(field).toHaveCSS('border-radius', '6px')
  await expect(field).toHaveCSS('font-family', /DM Sans/)
  await field.focus()
  // All form controls have either the shared focus halo or the keyboard outline.
  await expect.poll(() => field.evaluate(el => {
    const s = getComputedStyle(el)
    return s.outlineStyle === 'solid' && s.outlineColor === 'rgb(109, 74, 255)' || s.boxShadow.includes('109, 74, 255')
  })).toBe(true)
}

export async function expectEnterCard(card: Locator) {
  await expect(card).toHaveCSS('background-color', enterColors.surface)
  await expect(card).toHaveCSS('border-color', enterColors.border)
  await expect(card).toHaveCSS('border-radius', '10px')
}
