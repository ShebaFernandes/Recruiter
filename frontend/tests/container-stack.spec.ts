import { expect, test } from '@playwright/test'
import { execFileSync } from 'node:child_process'
import path from 'node:path'

// Opt-in only. This is the isolated local HTTPS stack, never a production account.
test.skip(process.env.ENTER_CONTAINER_STACK !== '1', 'Requires isolated container rehearsal')
test.use({ baseURL: 'https://localhost:8447', ignoreHTTPSErrors: true })

test('strict container stack: email verification through candidate submission', async ({ page }, info) => {
  test.setTimeout(120_000)
  const email = `browser-${Date.now()}@example.test`
  const password = 'Orchid!72-Cobalt!91-Zebra'
  await page.goto('/')
  await page.getByTestId('for-candidates').click()
  await page.getByLabel('Full name').fill('Synthetic Candidate')
  await page.getByLabel('Email', { exact: true }).fill(email)
  await page.getByLabel('Password', { exact: true }).fill(password)
  await page.getByRole('button', { name: 'Create account', exact: true }).click()
  await expect(page.getByRole('heading', { name: 'Check your email' })).toBeVisible()
  const inbox = await (await page.request.get('/test-mail/api/v1/messages')).json()
  const message = inbox.messages.find((item: { To: { Address: string }[] }) => item.To.some(to => to.Address === email))
  expect(message).toBeTruthy()
  const mail = await (await page.request.get(`/test-mail/api/v1/message/${message.ID}`)).json()
  const token = mail.Text.match(/[?&]verify-email=([^\s]+)/)[1]
  await page.goto(`/?verify-email=${token}`)
  await expect(page.getByRole('heading', { name: 'Start with your resume.' })).toBeVisible()
  const docx = execFileSync(path.resolve('../.venv/bin/python'), ['-c',
    'import sys;from scripts.container_stack_smoke import documents;sys.stdout.buffer.write(documents(sys.argv[1])[1])', email],
  { cwd: path.resolve('..'), env: process.env })
  await page.getByTestId('resume-input').setInputFiles({ name: 'fictional.docx', mimeType: 'application/vnd.openxmlformats-officedocument.wordprocessingml.document', buffer: docx })
  await expect(page.getByRole('heading', { name: "Here's how we understand you.", exact: true })).toBeVisible({ timeout: 60_000 })
  await expect(page.locator('.career-period')).toHaveCount(2)
  await page.getByRole('button', { name: 'View Resume', exact: true }).click()
  await expect(page.locator('.cp-docx')).toContainText('Synthetic Candidate')
  await page.getByRole('button', { name: 'Collapse resume' }).click()
  await page.getByRole('button', { name: "That's me ✓", exact: true }).click()
  const answer = page.getByLabel("What is the most meaningful thing you've built?", { exact: true })
  await answer.fill('Built a fictional service for this container test.')
  await answer.blur()
  await page.getByRole('button', { name: /Work preferences/ }).click()
  await page.getByRole('combobox', { name: 'Work setup' }).selectOption('Remote')
  await page.getByRole('button', { name: 'Update', exact: true }).click()
  await page.getByRole('button', { name: 'Confirm my profile', exact: true }).click()
  await page.getByRole('combobox', { name: 'First-time profile visibility' }).selectOption('approved_recruiters')
  await page.getByLabel('I agree to share my profile', { exact: false }).check()
  await page.getByRole('button', { name: "Yes, that's me ✓", exact: true }).click()
  await expect(page.getByRole('heading', { name: "You're in.", exact: true })).toBeVisible()
  for (const width of [1440, 390]) {
    await page.setViewportSize({ width, height: 900 })
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
    await page.screenshot({ path: info.outputPath(`container-success-${width}.png`), fullPage: true, animations: 'disabled' })
  }
  await page.reload()
  await expect(page.locator('.cp-identity')).toContainText('Synthetic Candidate')
  const csrf = await (await page.request.get('/api/v1/auth/csrf/')).json()
  const deleted = await page.request.delete('/api/v1/candidate/account/', {
    headers: { 'X-CSRFToken': csrf.csrfToken, Origin: 'https://localhost:8447' },
    data: { confirmation: 'DELETE', password },
  })
  expect(deleted.status()).toBe(204)
})
