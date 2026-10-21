import { expect, test } from '@playwright/test'
import { execFileSync } from 'node:child_process'
import path from 'node:path'
import { issueLocalAccountToken } from './account-token'

test('permanent preferences: responsive layout, inline editing and persistence', async ({ page, browser }, info) => {
  test.setTimeout(120_000)
  await page.addInitScript(() => sessionStorage.setItem('enter-door-intro-seen', '1'))
  const email = `preferences-${Date.now()}@example.test`
  await page.goto('/')
  await page.getByTestId('for-candidates').click()
  await page.getByLabel('Full name').fill('Jordan Test')
  await page.getByLabel('Email', { exact: true }).fill(email)
  await page.getByLabel('Password', { exact: true }).fill('Strong-pass-123!')
  await page.getByRole('button', { name: 'Create account', exact: true }).click()
  await expect(page.getByRole('heading', { name: 'Check your email' })).toBeVisible({ timeout: 20_000 })
  await page.goto(`/?verify-email=${issueLocalAccountToken(email, 'verify_email')}`)
  const file = execFileSync(path.resolve('../.venv/bin/python'), ['-c', `
import io,sys
from docx import Document
d=Document()
for line in ['Name: Jordan Test', 'Email: '+sys.argv[1], 'Role: Senior Engineer', 'Location: Bengaluru', '8 years of experience', 'Skills: Python, Django, PostgreSQL', 'Education: B.Tech, Example University', 'Experience: Senior Engineer|Example Studio|2020-01-01|Present|Built reliable services', 'Experience: Engineer|Sample Labs|2018-01-01|2019-12-01|Built APIs']:
    d.add_paragraph(line)
b=io.BytesIO();d.save(b);sys.stdout.buffer.write(b.getvalue())`, email])
  await page.getByTestId('resume-input').setInputFiles({ name: 'fictional.docx', mimeType: 'application/vnd.openxmlformats-officedocument.wordprocessingml.document', buffer: file })
  await expect(page.locator('.cp-identity')).toContainText('Jordan Test', { timeout: 40_000 })
  const panel = page.getByRole('complementary', { name: 'Career Settings panel' })
  await expect(panel).toBeVisible()
  await expect(page.locator('.cp-settings-toggle')).toHaveCount(0)
  await expect(panel.getByRole('button', { name: /close/i })).toHaveCount(0)
  await expect(page.getByRole('heading', { name: 'Career Settings', exact: true })).toHaveCount(0)
  await expect(panel.getByText('Role & direction', { exact: true })).toHaveCount(0)
  await expect(panel.getByRole('heading', { name: 'Build ↔ Lead Spectrum' })).toBeVisible()
  for (const name of ['Availability', 'Notice period', 'Compensation', 'Work preferences', 'How should we reach you?', 'Professional links']) {
    await panel.getByRole('button', { name: new RegExp(name.replace('?', '\\?')) }).first().click()
    await expect(panel.locator('form')).toBeVisible()
    await page.locator('.cp-welcome').click()
    await expect(panel.locator('form')).toHaveCount(0)
  }
  await panel.getByRole('button', { name: /Notice period.*Edit/ }).click()
  const update = page.waitForResponse(r => r.url().endsWith('/candidate/profile/') && r.request().method() === 'PATCH')
  await panel.getByLabel('Notice period').selectOption('30')
  expect((await update).status()).toBe(200)
  const slider = panel.getByRole('slider')
  await slider.focus()
  const spectrum = page.waitForResponse(r => r.url().endsWith('/candidate/profile/') && r.request().method() === 'PATCH')
  await slider.press('ArrowRight')
  expect((await spectrum).status()).toBe(200)
  await page.reload()
  await expect(panel.getByRole('button', { name: /Notice period.*30 days/ })).toBeVisible()
  await expect(slider).toHaveValue('75')
  await expect(panel.locator('.cp-spectrum-markers span')).toHaveCount(5)
  // Retain the native range's keyboard and pointer behavior after restyling.
  await slider.focus()
  const endSave = page.waitForResponse(r => r.url().endsWith('/candidate/profile/') && r.request().method() === 'PATCH')
  await slider.press('End')
  expect((await endSave).status()).toBe(200)
  await expect(slider).toHaveValue('100')
  const bounds = (await slider.boundingBox())!
  const dragSave = page.waitForResponse(r => r.url().endsWith('/candidate/profile/') && r.request().method() === 'PATCH')
  await page.mouse.move(bounds.x + bounds.width - 8, bounds.y + bounds.height / 2)
  await page.mouse.down()
  await page.mouse.move(bounds.x + 8, bounds.y + bounds.height / 2, { steps: 8 })
  await page.mouse.up()
  expect((await dragSave).status()).toBe(200)
  await expect(slider).toHaveValue('0')
  await page.reload()
  await expect(slider).toHaveValue('0')
  const mobileContext = await browser.newContext({ storageState: await page.context().storageState(), viewport: { width: 390, height: 844 }, hasTouch: true, isMobile: true, reducedMotion: 'reduce' })
  const mobilePage = await mobileContext.newPage()
  await mobilePage.goto(page.url())
  const mobileSlider = mobilePage.getByRole('slider', { name: 'Build and Lead preference' })
  await expect(mobileSlider).toHaveValue('0')
  await mobileSlider.scrollIntoViewIfNeeded()
  const mobileBounds = (await mobileSlider.boundingBox())!
  const touchSave = mobilePage.waitForResponse(r => r.url().endsWith('/candidate/profile/') && r.request().method() === 'PATCH')
  await mobilePage.touchscreen.tap(mobileBounds.x + mobileBounds.width / 2, mobileBounds.y + mobileBounds.height / 2)
  expect((await touchSave).status()).toBe(200)
  await mobilePage.reload()
  await expect(mobileSlider).toHaveValue('50')
  await mobilePage.getByRole('button', { name: /Work preferences.*Edit/ }).tap()
  await mobilePage.getByRole('combobox', { name: 'Preferred locations' }).fill('Mumbai')
  const locationsSave = mobilePage.waitForResponse(r => r.url().endsWith('/candidate/profile/') && r.request().method() === 'PATCH')
  await mobilePage.getByRole('option', { name: 'Mumbai', exact: true }).tap()
  expect((await locationsSave).status()).toBe(200)
  await mobilePage.reload()
  await expect(mobilePage.getByRole('button', { name: /Work preferences.*Mumbai.*Edit/ })).toBeVisible()
  await mobileContext.close()
  await expect(panel.getByLabel('Update Resume')).toBeAttached()
  await page.getByRole('button', { name: "That's me ✓" }).click()
  for (const width of [1440, 1024, 768, 390]) {
    await page.setViewportSize({ width, height: 1000 })
    await page.evaluate(() => window.scrollTo(0, 0))
    const main = (await page.locator('.cp-profile-main').boundingBox())!
    const settings = (await panel.boundingBox())!
    if (width >= 1024) expect(settings.x).toBeGreaterThanOrEqual(main.x + main.width)
    else expect(settings.y).toBeGreaterThanOrEqual(main.y + main.height)
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
    await page.screenshot({ path: info.outputPath(`permanent-preferences-${width}.png`), fullPage: true })
  }
})
