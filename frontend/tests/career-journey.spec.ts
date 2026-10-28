import { expect, test } from '@playwright/test'
import { spawnSync } from 'node:child_process'
import path from 'node:path'
import { issueLocalAccountToken } from './account-token'
import { provisionRecruiter } from './recruiter-admin'
import { dismissCareerPopover, expectDiscoverableCareerRoles, openCareerRole } from './career-role-assertions'

test.use({ hasTouch: true })

test('candidate and recruiter share the same interactive promotion journey', async ({ page }, info) => {
  test.setTimeout(180_000)
  const run = Date.now(), email = `journey-${run}@example.com`, password = 'strong-pass-123'
  const expected = [
    ['First Company', 'Software Engineer', 'Jan 2011 - Dec 2013'],
    ['Earlier Studio', 'Engineer', '2014-16'],
    ['Earlier Studio', 'Senior Engineer', '2016-17'],
    ['Earlier Studio', 'VP - Engineering', 'Jun 2017 - Apr 2019'],
    ['Northstar', 'Senior Engineer', 'May 2019 - Dec 2020'],
    ['Northstar', 'Engineering Manager', 'Jan 2021 - Mar 2023'],
    ['Northstar', 'Head of AI Engineering', 'Apr 2023 - Present'],
  ] as const
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
  const upload = page.waitForResponse(response => response.url().endsWith('/candidate/resumes/') && response.status() === 202)
  await page.getByTestId('resume-input').setInputFiles(docx)
  const resumeId = (await (await upload).json()).latest_resume.id
  expect(process.env.DATABASE_URL).toMatch(/\/test_enter_e2e_[a-f0-9]+$/)
  expect(process.env.RESUME_AI_ENABLED).toBe('false')
  const processed = spawnSync(path.resolve('../.venv/bin/python'), ['-c', `import django; django.setup()
from talent.models import ResumeProcessingJob
from talent.worker_runtime import run_bounded_job
job = ResumeProcessingJob.objects.get(resume_id=${resumeId})
assert run_bounded_job(job.pk) == 'completed'`], { cwd:path.resolve('../backend'), env:process.env, encoding:'utf8' })
  expect(processed.status, 'Offline fictional worker completes').toBe(0)
  const candidateTimeline = page.locator('.cp-career .career-journey')
  await expect(candidateTimeline.locator('.career-period > .career-job').first()).toBeVisible({ timeout: 30_000 })
  const profile = await (await page.request.get(`${process.env.PLAYWRIGHT_API_URL}/candidate/profile/`)).json()
  expect(profile.work_experiences).toHaveLength(expected.length)
  expect(new Set(profile.work_experiences.map((role: { id: number }) => role.id)).size).toBe(expected.length)
  await expectDiscoverableCareerRoles(page, candidateTimeline, expected)
  await expect(page.locator('.cp-identity')).toContainText('Head of AI Engineering')
  await expect(page.locator('.cp-skills').getByRole('heading', { name: 'Education' })).toHaveCount(0)
  for (const width of [1440, 390]) {
    await page.setViewportSize({ width, height: 900 })
    await expectDiscoverableCareerRoles(page, candidateTimeline, expected)
    const detail = await openCareerRole(page, candidateTimeline, 'Northstar', 'Head of AI Engineering')
    await expect(detail).toContainText('Apr 2023 — Present')
    await expect(detail).toBeInViewport()
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
    await page.screenshot({ path: info.outputPath(`candidate-journey-${width}.png`) })
    if (width === 390) {
      await dismissCareerPopover(candidateTimeline)
      const manager = await openCareerRole(page, candidateTimeline, 'Northstar', 'Engineering Manager')
      await expect(manager).toContainText('Jan 2021 — Mar 2023')
    }
    await dismissCareerPopover(candidateTimeline)
    await expect(page.getByRole('tooltip')).toHaveCount(0)
    await expect(page.getByRole('dialog', { name: /roles grouped here/ })).toHaveCount(0)
  }
  await expect(page.getByRole('combobox', { name: 'Profile Visibility' })).toHaveCount(0)
  await page.getByRole('button', { name: /Work preferences.*Edit/ }).click()
  await page.getByRole('checkbox', { name: 'Remote', exact:true }).check()
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
  await page.setViewportSize({ width: 1440, height: 900 })
  const graph = page.locator('.profile-drawer .career-journey')
  await expectDiscoverableCareerRoles(page, graph, expected)
  await expect(graph.locator('.career-period-line').first()).toHaveCSS('height', '3px')
  for (const width of [1440, 390]) {
    await page.setViewportSize({ width, height: 900 })
    await expectDiscoverableCareerRoles(page, graph, expected)
    const detail = await openCareerRole(page, graph, 'Northstar', 'Head of AI Engineering')
    await expect(detail).toContainText('Apr 2023 — Present')
    await expect(detail).toBeInViewport()
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
    await page.screenshot({ path: info.outputPath(`recruiter-journey-${width}.png`) })
    await dismissCareerPopover(graph)
    await expect(page.getByRole('tooltip')).toHaveCount(0)
    await expect(page.getByRole('dialog', { name: /roles grouped here/ })).toHaveCount(0)
  }
})
