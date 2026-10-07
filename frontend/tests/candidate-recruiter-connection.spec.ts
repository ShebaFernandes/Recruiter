import { expect, test } from '@playwright/test'
import { spawnSync } from 'node:child_process'
import path from 'node:path'

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
  await page.getByRole('link', { name: 'Verify this local account' }).click()
  await expect(page.getByRole('heading', { name: 'Drop your resume' })).toBeVisible()

  await page.getByTestId('resume-input').setInputFiles(pdfPath)
  await expect(page.getByRole('heading', { name: "We've built your starting profile" })).toBeVisible()
  await expect(page.locator('.about-card')).toContainText('Priya Nair')
  await expect(page.locator('.about-card')).toContainText('Backend Engineer')
  await expect(page.locator('.skills-card')).toContainText('Python')
  await expect(page.locator('.skills-card')).toContainText('Django')

  await page.getByRole('button', { name: /Complete my profile/ }).click()
  const quickStep = page.locator('.quick-step')
  await quickStep.getByRole('button', { name: '30 days' }).click()
  await quickStep.getByRole('button', { name: 'Remote', exact: true }).click()
  await quickStep.getByRole('button', { name: /Save and continue/ }).click()
  await quickStep.getByRole('button', { name: /Visible to approved recruiters/ }).click()
  await quickStep.getByRole('button', { name: 'Close quick completion' }).click()

  const experience = page.locator('.experience-card')
  await experience.getByRole('button', { name: 'Edit' }).click()
  await experience.getByRole('button', { name: 'Add experience' }).click()
  await experience.getByLabel('Experience company 1').fill('Audit Systems')
  await experience.getByLabel('Experience role 1').fill('Backend Engineer')
  await experience.getByLabel('Experience start 1').fill('2022-01-01')
  await experience.getByLabel('Experience highlights 1').fill('Built production Django APIs.')
  await experience.getByRole('button', { name: 'Save experience' }).click()

  const education = page.locator('.education-card')
  await education.getByRole('button', { name: 'Edit' }).click()
  await education.getByPlaceholder('One qualification per line').fill('B.Tech Computer Science, Audit University')
  await education.getByRole('button', { name: 'Save', exact: true }).click()

  const meaningful = page.locator('.proud-card')
  await meaningful.getByPlaceholder(/What did you build/).fill(meaningfulWork)
  await meaningful.getByRole('button', { name: 'Save my answer' }).click()

  await page.getByRole('button', { name: /Review & submit/ }).click()
  await page.locator('.review-submit').getByLabel('Profile-sharing consent').check()
  await page.locator('.review-submit').getByRole('button', { name: /Submit my profile/ }).click()
  await expect(page.getByRole('heading', { name: /You’re all set/ })).toBeVisible()

  await page.getByRole('button', { name: 'Log out' }).click()
  await page.getByTestId('for-recruiters').click()
  await page.getByLabel('Full name').fill('Audit Recruiter')
  await page.getByLabel('Company').fill('Audit Hiring')
  await page.getByLabel('Email').fill(recruiterEmail)
  await page.getByLabel('Password').fill(password)
  await page.getByRole('button', { name: 'Create account' }).click()
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
  await expect(profile.getByRole('link', { name: 'Resume' })).toBeVisible()
  await page.locator('.profile-drawer .close').click()

  await page.getByRole('button', { name: 'Log out' }).click()
  await page.getByTestId('for-candidates').click()
  await page.getByRole('button', { name: /Already have an account/ }).click()
  await page.getByLabel('Email').fill(candidateEmail)
  await page.getByLabel('Password').fill(password)
  await page.getByRole('button', { name: 'Log in', exact: true }).click()
  await page.getByTestId('resume-input').setInputFiles(pdfPath)
  await expect(page.getByText('Version 2')).toBeVisible()

  await page.getByRole('button', { name: 'Log out' }).click()
  await page.getByTestId('for-recruiters').click()
  await page.getByRole('button', { name: /Already have an account/ }).click()
  await page.getByLabel('Email').fill(recruiterEmail)
  await page.getByLabel('Password').fill(password)
  await page.getByRole('button', { name: 'Log in', exact: true }).click()
  await page.getByRole('button', { name: 'Candidate updates' }).click()
  await expect(page.locator('.workspace-sidepanel')).toContainText('Priya Nair')
  await expect(page.locator('.workspace-sidepanel')).toContainText('Updated resume')
})
