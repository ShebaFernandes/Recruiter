import { expect, test } from '@playwright/test'
import { spawnSync } from 'node:child_process'
import path from 'node:path'
import { issueLocalAccountToken } from './account-token'

test('candidate edits a saved role through the real API and keeps its ID after refresh', async ({ page }, info) => {
  test.skip(!/\/test_enter_e2e_[a-f0-9]+$/.test(process.env.DATABASE_URL || ''), 'Disposable PostgreSQL required')
  test.setTimeout(90_000)
  const email = `real-role-edit-${Date.now()}@example.test`
  await page.goto('/')
  await page.getByRole('button', { name: 'Join enter’s Talent network', exact: true }).click()
  await page.getByRole('button', { name: 'New here? Create an account' }).click()
  await page.getByLabel('Full name').fill('Role Edit Candidate')
  await page.getByLabel('Email', { exact: true }).fill(email)
  await page.getByLabel('Password', { exact: true }).fill('Role-edit-password-123!')
  const legal = page.getByRole('checkbox', { name: /at least 18 years old.*Terms of Use/i })
  if (await legal.count()) await legal.check()
  await page.getByRole('button', { name: 'Create account', exact: true }).click()
  await expect(page.getByRole('heading', { name: 'Check your email' })).toBeVisible({ timeout: 20_000 })
  await page.goto(`/?verify-email=${issueLocalAccountToken(email, 'verify_email')}`)
  const fixture = info.outputPath('fictional-role.docx')
  const created = spawnSync(path.resolve('../.venv/bin/python'), ['-c', `from docx import Document
document = Document()
for line in ['Name: Role Edit Candidate', 'Email: ${email}', 'Work Experience',
             'Experience: Software Engineer|Fictional Studio|2020-03-01|2022-09-01|Built services']:
    document.add_paragraph(line)
document.save(${JSON.stringify(fixture)})`], { encoding: 'utf8' })
  expect(created.status, created.stderr).toBe(0)
  const uploaded = page.waitForResponse(response => response.url().endsWith('/candidate/resumes/') && response.request().method() === 'POST')
  await page.getByTestId('resume-input').setInputFiles(fixture)
  const resumeId = (await (await uploaded).json()).latest_resume.id
  const processed = spawnSync(path.resolve('../.venv/bin/python'), ['-c', `import django; django.setup()
from talent.models import ResumeProcessingJob
from talent.worker_runtime import run_bounded_job
assert run_bounded_job(ResumeProcessingJob.objects.get(resume_id=${resumeId}).pk) == 'completed'`],
  { cwd: path.resolve('../backend'), env: { ...process.env, DJANGO_SETTINGS_MODULE: 'config.settings' }, encoding: 'utf8' })
  expect(processed.status, processed.stderr).toBe(0)
  const api = process.env.PLAYWRIGHT_API_URL
  const read = async () => (await (await page.request.get(`${api}/candidate/profile/`)).json())
  const before = await read()
  expect(before.work_experiences).toHaveLength(1)
  const roleId = before.work_experiences[0].id
  for (const width of [1440, 390]) {
    await page.setViewportSize({ width, height: 900 })
    const marker = page.getByRole('button', { name: /Software Engineer at Fictional Studio/ })
    await expect(marker).toBeVisible()
    await marker.click()
    await expect(page.getByRole('tooltip')).toContainText(width === 1440 ? 'Mar 2020 — Sep 2022' : 'Mar 2020 — Oct 2023')
    await page.getByRole('button', { name: 'Edit this role' }).click()
    const editor = page.getByRole('form', { name: /Edit Software Engineer/ })
    await expect(editor.getByRole('textbox', { name: 'Employer' })).toHaveValue('Fictional Studio')
    await expect(editor.getByRole('textbox', { name: 'Job title' })).toHaveValue('Software Engineer')
    await editor.screenshot({ path: info.outputPath(`restored-editor-${width}.png`) })
    if (width === 1440) {
      await expect(editor.getByLabel('Start date')).toHaveValue('2020-03')
      await editor.getByLabel('End date').fill('2023-10')
      const saved = page.waitForResponse(response => response.url().endsWith(`/candidate/work-experiences/${roleId}/`) && response.request().method() === 'PATCH')
      await editor.getByRole('button', { name: 'Save' }).click()
      expect((await saved).status()).toBe(200)
      await expect(page.getByText('Career Journey updated. Your changes are saved.')).toBeVisible()
    } else {
      await expect(editor.getByLabel('End date')).toHaveValue('2023-10')
      await editor.getByRole('button', { name: 'Cancel' }).click()
    }
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
  }
  const after = await read()
  expect(after.work_experiences).toHaveLength(1)
  expect(after.work_experiences[0].id).toBe(roleId)
  expect(after.work_experiences[0].end_date).toBe('2023-10-01')
  await page.reload()
  const marker = page.getByRole('button', { name: /Software Engineer at Fictional Studio/ })
  await marker.click()
  await expect(page.getByRole('tooltip')).toContainText('Mar 2020 — Oct 2023')
  const ambiguous = spawnSync(path.resolve('../.venv/bin/python'), ['-c', `import django
django.setup()
from talent.models import Resume
r = Resume.objects.get(pk=${resumeId}, candidate__user__email=${JSON.stringify(email)})
r.version = 2
r.extracted_data = {'_identity_issue': 'identity_unverified', '_identity_name_source': 'none'}
r.save(update_fields=['version', 'extracted_data'])`], { cwd: path.resolve('../backend'), encoding: 'utf8' })
  expect(ambiguous.status, ambiguous.stderr).toBe(0)
  await page.reload()
  await expect(page.getByRole('button', { name: 'Confirm ownership' })).toBeDisabled()
  await page.getByLabel('I confirm this exact resume is mine.').check()
  await page.getByLabel('Verify your account password').fill('wrong-password')
  const refused = page.waitForResponse(r => r.url().endsWith(`/candidate/resumes/${resumeId}/confirm-ownership/`) && r.request().method() === 'POST')
  await page.getByRole('button', { name: 'Confirm ownership' }).click()
  expect((await refused).status()).toBe(400)
  await expect(page.getByLabel('Verify your account password')).toHaveValue('')
  await page.getByLabel('Verify your account password').fill('Role-edit-password-123!')
  const accepted = page.waitForResponse(r => r.url().endsWith(`/candidate/resumes/${resumeId}/confirm-ownership/`) && r.request().method() === 'POST')
  await page.getByRole('button', { name: 'Confirm ownership' }).click()
  expect((await accepted).status()).toBe(200)
  await expect(page.getByText('Confirm this resume belongs to you')).toHaveCount(0)
  const protectedProfile = await read()
  expect(protectedProfile.work_experiences[0].company).toBe(after.work_experiences[0].company)
  expect(protectedProfile.work_experiences[0].end_date).toBe(after.work_experiences[0].end_date)
  expect(protectedProfile.work_experiences[0].id).toBe(before.work_experiences[0].id)

})
