import { expect, test } from '@playwright/test'
import { spawnSync } from 'node:child_process'
import { readFileSync } from 'node:fs'
import path from 'node:path'
import { issueLocalAccountToken } from './account-token'

test.use({ actionTimeout:10000 })
const cases = JSON.parse(readFileSync(path.resolve('../backend/tests/fixtures/employment-scenarios.json'), 'utf8')) as { name:string; lines:string[]; roles:number }[]
function offline(script: string) {
  if (!/\/test_enter_e2e_[a-f0-9]+$/.test(process.env.DATABASE_URL || '') || process.env.RESUME_AI_ENABLED !== 'false') throw new Error('Requires isolated offline E2E')
  const result = spawnSync(path.resolve('../.venv/bin/python'), ['-c', `import os
os.environ.setdefault('DJANGO_SETTINGS_MODULE','config.settings')
import django; django.setup()
${script}`], { cwd:path.resolve('../backend'), env:process.env, encoding:'utf8', timeout:30000 })
  expect(result.status, 'Offline fixture/worker completes; private diagnostics withheld').toBe(0)
  return result.stdout.trim()
}

for (const width of [390, 1440]) test(`latest resume evidence drives My Profile at ${width}px`, async ({ page, context }, info) => {
  test.setTimeout(240000)
  await page.setViewportSize({ width, height:1000 })
  await page.emulateMedia({ reducedMotion:'reduce' })
  for (const fixture of cases.filter(row => row.name !== 'unresolved')) {
    await context.clearCookies()
    const email = `journey-${fixture.name}-${width}-${Date.now()}@example.com`
    await page.goto('/')
    await page.getByTestId('for-candidates').click()
    await page.getByLabel('Full name').fill('Asha Rao')
    await page.getByLabel('Email', { exact:true }).fill(email)
    await page.getByLabel('Password', { exact:true }).fill('strong-pass-123')
    await page.getByRole('button', { name:'Create account', exact:true }).click()
    await expect(page.getByRole('heading', { name:'Check your email' })).toBeVisible({ timeout:20000 })
    await page.goto(`/?verify-email=${issueLocalAccountToken(email, 'verify_email')}`)
    await expect(page.getByRole('heading', { name:'Start with your resume' })).toBeVisible()
    const upload = async (name: string) => {
      const file = info.outputPath(`${name}.docx`)
      offline(`import json
from pathlib import Path
from tests.test_resume_reliability_matrix import _fixture_bytes
rows = json.loads(Path('tests/fixtures/employment-scenarios.json').read_text())
scenario = next(row for row in rows if row['name'] == ${JSON.stringify(name)})
Path(${JSON.stringify(file)}).write_bytes(_fixture_bytes('docx', ['Name: Asha Rao', *scenario['lines']]))`)
      const response = page.waitForResponse(r => r.url().endsWith('/candidate/resumes/') && r.request().method() === 'POST')
      await page.getByTestId('resume-input').setInputFiles(file)
      const accepted = await response
      expect(accepted.status()).toBe(202)
      const resumeId = (await accepted.json()).latest_resume.id
      expect(offline(`from talent.models import ResumeProcessingJob
from talent.worker_runtime import run_bounded_job
job = ResumeProcessingJob.objects.get(resume_id=${resumeId})
print(run_bounded_job(job.pk))
assert not job.resume.ai_usage.exists()`)).toBe('completed')
      await expect(page.getByRole('heading', { name:"Here's how we understand you." })).toBeVisible({ timeout:20000 })
      const api = await (await page.request.get(`${process.env.PLAYWRIGHT_API_URL}/candidate/profile/`)).json()
      expect(api.latest_resume.id).toBe(resumeId)
      expect(api.latest_resume.processing_status).toBe('completed')
      return api
    }
    const saved = await upload(fixture.name)
    const journey = page.locator('.cp-career')
    expect(saved.work_experiences).toHaveLength(fixture.roles)
    expect(saved.employment_extraction.verified_role_ids).toHaveLength(fixture.roles)
    expect(saved.employment_extraction.source).toBe('rules')
    await expect(journey.locator('.career-period')).toHaveCount(fixture.roles)
    if (fixture.roles) {
      await expect(journey.getByRole('status')).toHaveCount(0)
      for (const role of saved.work_experiences) {
        const names = await journey.locator('.career-period button').evaluateAll(els=>els.map(el=>el.getAttribute('aria-label')).join(' '))
        expect(names).toContain(role.company)
        expect(names).toContain(role.role)
        await expect(journey.locator('.career-journey')).not.toContainText(role.company)
      }
      const button = journey.locator('.career-period button').first()
      await button.focus()
      await expect(page.getByRole('tooltip')).toBeVisible()
      await page.keyboard.press('Escape')
      await button.click()
      await expect(page.getByRole('tooltip')).toBeVisible()
      await page.keyboard.press('Escape')
    } else {
      expect(saved.employment_extraction.status).toBe('confirmed_no_employment')
      await expect(journey.getByRole('status')).toContainText('No employment history declared in the latest resume')
    }
    if (fixture.name === 'internship') await expect(journey.locator('.is-internship')).toHaveCount(1)
    if (['promotions', 'internship'].includes(fixture.name)) await expect(journey.locator('.career-gap-period')).toHaveCount(0)
    if (fixture.name === 'overlap-gap') {
      await expect(journey.locator('.career-gap-period')).toHaveCount(1)
      await expect(journey.locator('button[aria-label*="overlapping employment"]')).toHaveCount(1)
    }
    if (fixture.name === 'partial') {
      await expect(journey.locator('.career-period button')).toHaveAttribute('aria-label', /not specified/)
      expect(saved.work_experiences[0].start_date).toBeNull()
    }
    if (fixture.name === 'single') {
      const line = await journey.locator('.career-period-line').boundingBox()
      expect(line!.width).toBeGreaterThan(200)
    }
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
    await journey.scrollIntoViewIfNeeded()
    await page.screenshot({ path:info.outputPath(`${fixture.name}-${width}.png`), animations:'disabled' })
    if (fixture.name === 'promotions') {
      const unresolved = await upload('unresolved')
      expect(unresolved.work_experiences).toEqual(saved.work_experiences)
      expect(unresolved.employment_extraction.status).toBe('review_required')
      expect(unresolved.employment_extraction.verified_role_ids).toEqual([])
      await expect(journey.locator('.career-period')).toHaveCount(saved.work_experiences.length)
      await expect(journey.getByRole('status')).toContainText('Review is needed')
      await expect(journey.locator('.career-sequence.needs-review')).toHaveCount(saved.work_experiences.length)
      await journey.scrollIntoViewIfNeeded()
      await page.screenshot({ path:info.outputPath(`preserved-review-${width}.png`), animations:'disabled' })
    }
  }
})
