import { expect, test } from '@playwright/test'
import { spawnSync } from 'node:child_process'
import path from 'node:path'
import { issueLocalAccountToken } from './account-token'
import { provisionRecruiter } from './recruiter-admin'

test.use({ hasTouch: true })

test('candidate and recruiter share the same interactive promotion journey', async ({ page }, info) => {
  test.setTimeout(120_000)
  const run = Date.now(), email = `journey-${run}@example.com`, password = 'strong-pass-123'
  const docx = info.outputPath('fictional-promotions.docx')
  const created = spawnSync(path.resolve('../.venv/bin/python'), ['-c', `
import os; os.environ.setdefault('DJANGO_SETTINGS_MODULE','config.settings')
import django; django.setup()
from docx import Document
from tests.test_resume_promotions import promotion_lines
d=Document()
for line in promotion_lines(): d.add_paragraph(line)
d.save(${JSON.stringify(docx)})
`], { cwd: path.resolve('../backend'), encoding: 'utf8' })
  expect(created.status).toBe(0)
  await page.goto('/')
  await page.getByTestId('for-candidates').click()
  await page.getByLabel('Full name').fill('Journey Test Candidate')
  await page.getByLabel('Email', { exact: true }).fill(email)
  await page.getByLabel('Password', { exact: true }).fill(password)
  await page.getByRole('button', { name: 'Create account', exact: true }).click()
  await expect(page.getByRole('heading', { name: 'Check your email' })).toBeVisible({ timeout: 20_000 })
  await page.goto(`/?verify-email=${issueLocalAccountToken(email, 'verify_email')}`)
  await page.getByTestId('resume-input').setInputFiles(docx)
  await expect(page.locator('.career-period')).toHaveCount(7, { timeout: 30_000 })
  await expect(page.locator('.career-laptop')).toHaveCount(7)
  await expect(page.locator('.cp-identity')).toContainText('Head of AI Engineering')
  await expect(page.locator('.cp-profile-main')).toContainText('AI Engineering Leadership')
  await expect(page.locator('.cp-skills').getByRole('heading', { name: 'Education' })).toHaveCount(0)
  const labels = await page.locator('.career-period .career-job').evaluateAll(items => items.map(item => item.getAttribute('aria-label')))
  for (const width of [1440, 1024, 768, 390]) {
    await page.setViewportSize({ width, height: 900 })
    const marker = page.getByRole('button', { name: /Head of AI Engineering at Northstar/ })
    await marker.scrollIntoViewIfNeeded()
    if (width > 640) await marker.hover(); else await marker.tap()
    await expect(page.getByRole('tooltip')).toContainText('Apr 2023 - Present')
    await expect(page.getByRole('tooltip')).toContainText('Built a reliable workflow service used by 12 teams.')
    await expect(marker).toHaveClass(/is-active/)
    await expect(page.getByRole('tooltip')).toBeInViewport()
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
    await page.screenshot({ path: info.outputPath(`candidate-journey-${width}.png`) })
    if (width === 390) {
      await page.getByRole('button', { name: /Engineering Manager at Northstar/ }).tap()
      await expect(page.getByRole('tooltip')).toContainText('Engineering Manager')
      await expect(page.getByRole('tooltip')).toContainText('Jan 2021 - Mar 2023')
    }
    await page.keyboard.press('Escape')
    await expect(page.getByRole('tooltip')).toHaveCount(0)
  }
  await expect(page.getByRole('combobox', { name: 'Profile Visibility' })).toHaveCount(0)
  await page.getByRole('button', { name: /Work preferences.*Edit/ }).click()
  await page.getByRole('combobox', { name: 'Work setup' }).selectOption('Remote')
  await expect(page.locator('.cp-autosave-status')).toHaveText('Saved')
  await page.getByRole('button', { name: /Notice period.*Edit/ }).click()
  await page.getByRole('combobox', { name: 'Notice period' }).selectOption('30')
  await page.locator('.cp-welcome').click()
  await expect(page.locator('.cp-settings-inline-editor')).toHaveCount(0)
  await page.getByRole('button', { name: 'Confirm my profile' }).click()
  await page.getByRole('combobox', { name: 'First-time profile visibility' }).selectOption('approved_recruiters')
  await page.getByLabel('I agree to share my profile', { exact: false }).check()
  await page.getByRole('button', { name: "Yes, that's me ✓" }).click()
  await expect(page.getByRole('heading', { name: "You're in." })).toBeVisible()
  await page.getByRole('button', { name: 'Log out' }).click()
  const recruiter = `journey-recruiter-${run}@example.com`
  provisionRecruiter(recruiter, password)
  await page.getByTestId('for-recruiters').click()
  await page.getByLabel('Email', { exact: true }).fill(recruiter)
  await page.getByLabel('Password', { exact: true }).fill(password)
  await page.getByRole('button', { name: 'Log in', exact: true }).click()
  await page.getByLabel('Candidate search').fill('AI engineer in Pune with Python')
  await page.getByRole('button', { name: 'Search talent' }).click()
  await page.locator('.candidate-card').filter({ hasText: 'Journey Test Candidate' }).first().getByRole('button', { name: 'View profile' }).click()
  const graph = page.locator('.profile-drawer .career-journey')
  await expect(graph.locator('.career-period')).toHaveCount(7)
  await expect(graph.locator('.career-laptop')).toHaveCount(7)
  await expect(graph.locator('.career-period-line').first()).toHaveCSS('height', '3px')
  expect(await graph.locator('.career-period .career-job').evaluateAll(items => items.map(item => item.getAttribute('aria-label')))).toEqual(labels)
  for (const width of [1440, 1024, 768, 390]) {
    await page.setViewportSize({ width, height: 900 })
    const marker = graph.getByRole('button', { name: /Head of AI Engineering at Northstar/ })
    await marker.scrollIntoViewIfNeeded()
    await marker.click()
    await expect(page.getByRole('tooltip')).toContainText('Apr 2023 - Present')
    await expect(page.getByRole('tooltip')).toBeInViewport()
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
    await page.screenshot({ path: info.outputPath(`recruiter-journey-${width}.png`) })
    await marker.click()
    await expect(page.getByRole('tooltip')).toHaveCount(0)
  }
})
