import { expect, test } from '@playwright/test'
import { execFileSync } from 'node:child_process'
import path from 'node:path'
import { issueLocalAccountToken } from './account-token'

test('permanent preferences: responsive layout, inline editing and persistence', async ({ page }, info) => {
  test.setTimeout(120_000)
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
    await panel.getByRole('button', { name: 'Cancel', exact: true }).click()
  }
  await panel.getByRole('button', { name: /Notice period.*Edit/ }).click()
  await panel.getByLabel('Notice period').selectOption('30')
  const update = page.waitForResponse(r => r.url().endsWith('/candidate/profile/') && r.request().method() === 'PATCH')
  await panel.getByRole('button', { name: 'Update', exact: true }).click()
  expect((await update).status()).toBe(200)
  const slider = panel.getByRole('slider')
  await slider.focus()
  const spectrum = page.waitForResponse(r => r.url().endsWith('/candidate/profile/') && r.request().method() === 'PATCH')
  await slider.press('ArrowRight')
  expect((await spectrum).status()).toBe(200)
  await page.reload()
  await expect(panel.getByRole('button', { name: /Notice period.*30 days/ })).toBeVisible()
  await expect(slider).toHaveValue('75')
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
