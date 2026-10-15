import { provisionRecruiter } from './recruiter-admin'
import { expect, test, type Download } from '@playwright/test'
import { readFile } from 'node:fs/promises'
import { spawnSync } from 'node:child_process'
import path from 'node:path'
import { issueLocalAccountToken } from './account-token'

test.skip(process.env.RUN_CONNECTION_AUDIT !== '1', 'Run explicitly against an isolated audit database.')

function createRealPdf(destination: string) {
  const python = path.resolve('../.venv/bin/python')
  const backend = path.resolve('../backend')
  const script = [
    "import os; os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')",
    'import django; django.setup()',
    'from pathlib import Path',
    'from tests.test_candidate_flow import resume_pdf',
    `Path(${JSON.stringify(destination)}).write_bytes(resume_pdf())`,
  ].join('; ')
  const result = spawnSync(python, ['-c', script], { cwd: backend, encoding: 'utf8' })
  if (result.status !== 0) throw new Error(result.stderr || 'Could not create PDF fixture.')
}

test('candidate created in the UI is discovered and updated in the recruiter UI', async ({ page }, testInfo) => {
  test.setTimeout(120_000)
  const runId = Date.now()
  const candidateEmail = `connection-candidate-${runId}@example.com`
  const recruiterEmail = `connection-recruiter-${runId}@example.com`
  const password = 'strong-pass-123'
  const meaningfulWork = 'Built a production event-processing service with measurable reliability gains.'
  const pdfPath = testInfo.outputPath('priya-real-resume.pdf')
  createRealPdf(pdfPath)

  await page.goto('/')
  await page.getByTestId('for-candidates').click()
  await page.getByLabel('Full name').fill('Connection Candidate')
  await page.getByLabel('Email').fill(candidateEmail)
  await page.getByLabel('Password').fill(password)
  await page.getByRole('button', { name: 'Create account' }).click()
  await expect(page.getByRole('heading', { name: 'Check your email' })).toBeVisible({ timeout: 20_000 })
  await page.goto(`/?verify-email=${issueLocalAccountToken(candidateEmail, 'verify_email')}`)
  await expect(page.getByRole('heading', { name: 'Start with your resume.' })).toBeVisible()

  await page.getByTestId('resume-input').setInputFiles(pdfPath)
  await expect(page.locator('.cp-identity')).toContainText('Priya Nair', { timeout: 30_000 })
  await expect(page.locator('.cp-identity')).toContainText('Backend Engineer')
  await expect(page.locator('.cp-signals')).toContainText('Python')
  await expect(page.locator('.cp-signals')).toContainText('Django')
  await page.getByRole('button', { name: 'Not quite — edit' }).click()
  await page.getByRole('button', { name: 'Add experience', exact: true }).click()
  await page.getByLabel('Company 1', { exact: true }).fill('Audit Systems')
  await page.getByLabel('Job title 1', { exact: true }).fill('Backend Engineer')
  await page.getByLabel('Start date 1', { exact: true }).fill('2022-01-01')
  await page.getByLabel('Education (one entry per line)').fill('B.Tech Computer Science, Audit University')
  await page.getByRole('button', { name: 'Save corrections' }).click()
  await expect(page.getByRole('button', { name: /Backend Engineer at Audit Systems/ })).toBeVisible()
  await page.getByLabel("What is the most meaningful thing you've built?").fill(meaningfulWork)
  const answerSaved = page.waitForResponse(r => r.url().endsWith('/candidate/profile/') && r.request().method() === 'PATCH')
  await page.getByRole('button', { name: 'Save answer' }).click()
  expect((await answerSaved).status()).toBe(200)
  await page.getByLabel('Notice Period (days)').fill('30')
  await page.getByLabel('Remote', { exact: true }).check()
  await expect(page.getByRole('combobox', { name: 'Profile Visibility' })).toHaveCount(0)
  await page.getByRole('button', { name: 'Confirm my profile' }).click()
  await expect(page.getByRole('heading', { name: "Here's how we'll remember you" })).toBeVisible()
  await page.getByRole('combobox', { name: 'First-time profile visibility' }).selectOption('approved_recruiters')
  await expect(page.getByRole('button', { name: "Yes, that's me ✓" })).toBeEnabled()
  await page.getByLabel('I agree to share my profile', { exact: false }).check()
  await page.getByRole('button', { name: "Yes, that's me ✓" }).click()
  await expect(page.getByRole('heading', { name: "You're in." })).toBeVisible()
  await page.getByRole('button', { name: 'Log out' }).click()
  await page.getByTestId('for-recruiters').click()
  provisionRecruiter(recruiterEmail, password)
  await page.getByLabel('Email').fill(recruiterEmail)
  await page.getByLabel('Password').fill(password)
  await page.getByRole('button', { name: 'Log in', exact: true }).click()
  await page.getByLabel('Candidate search').fill('Backend engineer with 4 years experience')
  await page.getByRole('button', { name: 'Search talent' }).click()
  await page.getByRole('button', { name: 'Let me type it' }).click()
  await page.getByLabel('Clarification answer').fill('Pune')
  await page.getByRole('button', { name: /Continue/ }).click()
  // Re-running this audit against the same isolated database can leave an older
  // Priya Nair record behind. Results are newest-first, so target the record
  // created by this run without requiring production display names to be unique.
  const candidateCard = page.locator('.candidate-card').filter({ hasText: 'Priya Nair' }).first()
  await expect(candidateCard).toBeVisible()
  await expect(candidateCard).toContainText('Backend Engineer')
  await expect(candidateCard).toContainText('Pune')
  await candidateCard.getByRole('button', { name: 'View profile' }).click()
  const profile = page.locator('.profile-drawer')
  await expect(profile).toContainText('Audit Systems')
  await expect(profile).toContainText(meaningfulWork)
  await expect(profile.getByRole('button', { name: 'View Resume' })).toBeVisible()
  const resumeResponse = page.waitForResponse(response => /\/resumes\/\d+\/download\/$/.test(response.url()))
  let previewDownload: Download | undefined
  page.on('download', download => { previewDownload = download })
  page.context().on('page', newPage => newPage.on('download', download => { previewDownload = download }))
  const popupEvent = page.waitForEvent('popup')
  await profile.getByRole('button', { name: 'View Resume' }).click()
  const popup = await popupEvent
  const document = await resumeResponse
  expect(document.status()).toBe(200)
  expect(document.headers()['content-type']).toContain('application/pdf')
  // Headless Chromium can download PDFs instead of using its native viewer.
  await expect.poll(() => previewDownload || popup.url().startsWith('blob:')).toBeTruthy()
  const signature = previewDownload
    ? (await readFile((await previewDownload.path())!)).subarray(0, 4).toString()
    : await page.evaluate(async url => (await (await fetch(url)).text()).slice(0, 4), popup.url())
  expect(signature).toBe('%PDF')
  await popup.close()
  await page.locator('.profile-drawer .close').click()

  await page.getByRole('button', { name: 'Log out' }).click()
  await page.getByTestId('for-candidates').click()
  await page.getByRole('button', { name: /Already have an account/ }).click()
  await page.getByLabel('Email').fill(candidateEmail)
  await page.getByLabel('Password').fill(password)
  await page.getByRole('button', { name: 'Log in', exact: true }).click()
  await page.getByTestId('resume-input').setInputFiles(pdfPath)
  await expect(page.getByRole('heading', { name: "Here's how we understand you.", exact: true })).toBeVisible({ timeout: 30_000 })
  await expect(page.getByRole('heading', { name: 'Review resume changes' })).toHaveCount(0)

  await page.getByRole('button', { name: 'Log out' }).click()
  await page.getByTestId('for-recruiters').click()
  await page.getByLabel('Email').fill(recruiterEmail)
  await page.getByLabel('Password').fill(password)
  await page.getByRole('button', { name: 'Log in', exact: true }).click()
  await page.getByRole('button', { name: 'Candidate updates' }).click()
  await expect(page.locator('.workspace-sidepanel')).toContainText('Priya Nair')
  await expect(page.locator('.workspace-sidepanel')).toContainText('Updated resume')
})
