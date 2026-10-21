import { expect, test, type Page, type TestInfo } from '@playwright/test'
import type { Candidate } from '../src/types'

test.use({ video: { mode: 'on', size: { width: 1440, height: 1000 } } })
test.describe('upload media', () => {
  test('background playback, responsive placement and safe fallbacks', async ({ page }, info) => {
    test.setTimeout(60_000)
    const errors: string[] = []
    page.on('pageerror', error => errors.push(error.message))
    await page.route('**/api/v1/**', route => {
      const path = new URL(route.request().url()).pathname
      if (path.endsWith('/auth/me/')) return route.fulfill({ json: { id: 9001, full_name: profile.full_name, email: profile.email, role: 'candidate' } })
      if (path.endsWith('/candidate/profile/')) return route.fulfill({ json: { ...profile, latest_resume: null } })
      return route.fulfill({ json: {} })
    })
    await page.goto('/')
    await expect(page.getByRole('heading', { name: 'ENTER what’s next?' })).toBeVisible()
    const background = page.locator('.platform-background')
    const video = background.locator('video')
    const input = page.getByTestId('resume-input')
    await expect(background).toHaveAttribute('data-render-state', 'running')
    await expect(video).toHaveJSProperty('muted', true)
    await expect(video).toHaveJSProperty('loop', true)
    await expect(video).toHaveCSS('object-fit', 'cover')
    await expect(video).toHaveCSS('object-position', '50% 100%')
    await expect(video).toHaveAttribute('src', 'https://d8j0ntlcm91z4.cloudfront.net/user_38xzZboKViGWJOttwIXH07lWA1P/hf_20260820_010308_b1636845-4c15-4ab6-b0c9-9a29bfb0c6e3.mp4')
    const currentTime = () => video.evaluate((el: HTMLVideoElement) => el.currentTime)
    const firstTime = await currentTime()
    await page.waitForTimeout(1200)
    expect(await currentTime()).not.toBe(firstTime)
    await expect(background).toHaveCSS('position', 'fixed')
    for (const width of [1440, 1024, 768, 390]) {
      await page.setViewportSize({ width, height: 1000 })
      await expect(background).toHaveCount(1)
      expect(await background.boundingBox()).toEqual({ x: 0, y: 0, width, height: 1000 })
      await expect(background).toHaveCSS('pointer-events', 'none')
      expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
      const picker = page.waitForEvent('filechooser')
      await page.locator('.onboarding-choose').click()
      await picker
      await capture(page, info, `upload-${width}`)
    }
    await page.getByRole('button', { name: 'Pause background animation' }).click()
    await expect(background).toHaveAttribute('data-render-state', 'paused')
    const pausedTime = await currentTime()
    await page.waitForTimeout(200)
    expect(await currentTime()).toBe(pausedTime)
    await page.getByRole('button', { name: 'Play background animation' }).click()
    await expect(background).toHaveAttribute('data-render-state', 'running')
    await page.evaluate(() => { Object.defineProperty(document, 'hidden', { configurable: true, value: true }); document.dispatchEvent(new Event('visibilitychange')) })
    await expect(background).toHaveAttribute('data-render-state', 'paused')
    await page.evaluate(() => { Reflect.deleteProperty(document, 'hidden'); document.dispatchEvent(new Event('visibilitychange')) })
    await expect(background).toHaveAttribute('data-render-state', 'running')
    await page.emulateMedia({ reducedMotion: 'reduce' })
    await expect(background).toHaveAttribute('data-render-state', 'fallback')
    await expect(video).toHaveCount(0)
    await expect(input).toBeEnabled()
    await capture(page, info, 'reduced-motion')
    await page.emulateMedia({ reducedMotion: 'no-preference' })
    await page.route('**/hf_20260820_010308_b1636845-4c15-4ab6-b0c9-9a29bfb0c6e3.mp4', route => route.abort())
    await page.reload()
    await expect(background).toHaveAttribute('data-render-state', 'fallback')
    await expect(video).toHaveCount(0)
    await expect(input).toBeEnabled()
    await capture(page, info, 'media-unavailable')
    expect(errors).toEqual([])
  })
})
const profile = {
  id: 9001, full_name: 'Jordan Taylor', headline: 'Senior Platform Engineer',
  current_company: 'Example Studio', email: 'jordan@example.test', phone: '',
  location: 'Bengaluru', total_experience: '8.0', notice_period_days: 30,
  current_salary_lpa: '20.00', expected_salary_lpa: '30.00', employment_type: 'Full-time',
  linkedin_url: '', github_url: '', summary: '', meaningful_work: 'A reliable service that helps teams work together.',
  visibility: 'approved_recruiters', work_preferences: ['Hybrid'], skills: ['Agentic AI', 'LangGraph', 'Redis', 'Generative AI', 'Distributed Systems'],
  education: ['B.Tech, Example University'], profile_status: 'draft', profile_updated_at: '2026-10-01T00:00:00Z',
  build_lead_preference: 50, profile_photo_url: null, submission_missing_fields: [], missing_fields: [], can_submit: true,
  career_preferences: { availability: 'Open to the right opportunity', preferred_locations: ['Bengaluru'], contact_preferences: ['Email'], standout_signal: 'Built a reliable service for internal teams.', motivators: ['Exceptional team'] },
  work_experiences: [
    { id: 1, company: 'Sample Labs', role: 'Engineer', start_date: '2018-01-01', end_date: '2019-12-31', description: 'Built internal tools.', gap_reason: '' },
    { id: 2, company: 'Example Studio', role: 'Senior Platform Engineer', start_date: '2020-01-01', end_date: null, description: 'Built reliable services.', gap_reason: '' },
  ],
  latest_resume: { id: 1, original_name: 'Jordan-Taylor.docx', version: 1, uploaded_at: '2026-10-01T00:00:00Z', processing_status: 'completed', scan_status: 'clean', processing_error: '', can_retry: false, url: '/api/v1/resumes/1/download/' },
} as Candidate

test('glass surfaces retain readable content over moving video', async ({ page }, info) => {
  test.setTimeout(120_000)
  let signedIn = false
  await page.route('**/api/v1/**', route => {
    if (route.request().url().endsWith('/auth/me/')) return route.fulfill({ status:signedIn ? 200 : 401, json:signedIn ? { id:9001, full_name:profile.full_name, email:profile.email, role:'candidate' } : {} })
    return route.fulfill({ json:profile })
  })
  for (const width of [1440,1024,768,390]) {
    await page.setViewportSize({ width, height:1000 })
    signedIn = false
    await page.goto('/')
    await page.getByTestId('for-candidates').click()
    await expect(page.locator('.auth-card')).toHaveCSS('background-color','rgba(250, 248, 244, 0.94)')
    await expect(page.locator('.auth-card')).toHaveCSS('backdrop-filter','blur(5px) saturate(1.1)')
    await expect(page.locator('.auth-story__copy')).toHaveCSS('background-color','rgba(0, 0, 0, 0)')
    await expect(page.getByRole('button', { name:'Create account', exact:true })).toHaveCSS('background-color','rgb(48, 56, 66)')
    if (width >= 1024) {
      const story = await page.locator('.auth-story').boundingBox()
      const card = await page.locator('.auth-card').boundingBox()
      expect(Math.abs(story!.y - card!.y)).toBeLessThan(24)
    }
    await capture(page,info,`signup-${width}`)
    await page.locator('.platform-background video').evaluate(async (el:HTMLVideoElement)=>{
      el.pause()
      await new Promise<void>(resolve=>{el.addEventListener('seeked',()=>resolve(),{once:true}); el.currentTime=el.duration*.9})
    })
    await page.screenshot({path:info.outputPath(`signup-${width}-late-frame.png`)})
    await page.goto('/recruiter')
    await expect(page.locator('.auth-card')).toHaveCSS('background-color','rgba(250, 248, 244, 0.94)')
    await capture(page,info,`recruiter-login-${width}`)
    signedIn = true
    await page.reload()
    await expect(page.locator('.cp-identity-card')).toBeVisible()
    await expect(page.locator('.cp-profile')).toHaveCSS('background-color','rgba(0, 0, 0, 0)')
    for (const selector of ['.cp-identity-card','.cp-career-surface','.cp-resume-row']) {
      await expect(page.locator(selector)).toHaveCSS('background-color','rgba(250, 248, 244, 0.94)')
      await expect(page.locator(selector)).toHaveCSS('backdrop-filter','blur(5px) saturate(1.1)')
      await expect(page.locator(selector)).toHaveCSS('opacity','1')
    }
    await expect(page.locator('.cp-professional-read')).toHaveCSS('background-color','rgba(229, 246, 243, 0.93)')
    await expect(page.locator('.cp-settings')).toHaveCSS('background-color','rgba(250, 248, 244, 0.96)')
    const video = page.locator('.platform-background video')
    await expect(page.locator('.platform-background')).toHaveAttribute('data-render-state','running')
    const start = await video.evaluate((el:HTMLVideoElement)=>el.currentTime)
    await page.waitForTimeout(600)
    expect(await video.evaluate((el:HTMLVideoElement)=>el.currentTime)).not.toBe(start)
    await capture(page,info,`profile-${width}`)
    for (const fraction of [.1,.5,.9]) {
      await video.evaluate(async (el:HTMLVideoElement,fraction)=>{
        el.pause()
        await new Promise<void>(resolve=>{ el.addEventListener('seeked',()=>resolve(),{once:true}); el.currentTime=el.duration*fraction })
      },fraction)
      await page.screenshot({path:info.outputPath(`profile-${width}-frame-${fraction}.png`)})
    }
    await page.locator('.cp-career').scrollIntoViewIfNeeded()
    await page.screenshot({path:info.outputPath(`landscape-behind-cards-${width}.png`)})
    await expect(page.locator('.cp-replace-control > svg')).toBeVisible()
    await page.locator('.cp-footer').scrollIntoViewIfNeeded()
    await expect(page.locator('.cp-footer')).toHaveCSS('background-color','rgba(0, 0, 0, 0)')
    await page.screenshot({path:info.outputPath(`footer-${width}.png`)})
    expect(await page.evaluate(()=>document.documentElement.scrollWidth)).toBeLessThanOrEqual(width)
  }
})

test('compact status and location selection saves and closes suggestions', async ({ page }, info) => {
  let saved = profile
  await page.route('**/api/v1/**', async route => {
    if (route.request().url().endsWith('/auth/me/')) return route.fulfill({ json:{ id:9001, full_name:profile.full_name, email:profile.email, role:'candidate' } })
    if (route.request().method() === 'PATCH') {
      const patch = route.request().postDataJSON()
      saved = { ...saved, ...patch, career_preferences:{ ...saved.career_preferences, ...patch.career_preferences } }
    }
    return route.fulfill({ json:saved })
  })
  for (const width of [1440,390]) {
    await page.setViewportSize({width,height:1000})
    await page.goto('/')
    await expect(page.locator('[data-setting=availability]')).not.toContainText('Edit')
    await expect(page.locator('.cp-career-heading p')).toHaveCSS('font-size','11px')
    await page.locator('[data-setting=work_preferences]').click()
    const location = width === 1440 ? 'Hyderabad' : 'Pune'
    await page.getByRole('combobox', {name:'Preferred locations'}).fill(location)
    await page.getByRole('option', {name:location,exact:true}).click()
    await expect(page.getByRole('listbox')).toHaveCount(0)
    await expect(page.getByRole('button',{name:`Remove ${location}`})).toBeVisible()
    await expect.poll(()=>saved.career_preferences.preferred_locations).toContain(location)
    await page.locator('.cp-settings-panel').screenshot({path:info.outputPath(`compact-settings-${width}.png`)})
  }
})

test('settings highlights and compact focus treatment', async ({ page }, info) => {
  await page.route('**/api/v1/**', route => route.fulfill({ json: route.request().url().endsWith('/auth/me/') ? { id: 9001, full_name: profile.full_name, email: profile.email, role: 'candidate' } : profile }))
  await page.goto('/')
  const status = page.locator('[data-setting="availability"]')
  await expect(status).toHaveCSS('background-color', 'rgba(229, 246, 243, 0.93)')
  await expect(page.locator('.cp-replace-control')).toHaveCSS('background-color', 'rgba(229, 246, 243, 0.93)')
  await expect(page.locator('.cp-read-wordmark')).toHaveCSS('width', '40px')
  for (const width of [1440, 390]) {
    await page.setViewportSize({ width, height: 1000 })
    await status.click()
    await expect(page.getByText('Job Search Status', { exact: true })).toHaveCount(1)
    const choice = page.getByRole('radio', { name: 'Actively Looking', exact: true })
    await page.keyboard.press('Tab')
    await choice.focus()
    const pill = choice.locator('..')
    await expect(pill).toHaveCSS('outline-style', 'solid')
    const sizes = await page.locator('#settings-editor-availability .cp-choice').evaluateAll(nodes => nodes.map(node => ({ width:node.getBoundingClientRect().width, height:node.getBoundingClientRect().height })))
    expect(new Set(sizes.map(size => size.width)).size).toBe(1)
    expect(new Set(sizes.map(size => size.height)).size).toBe(1)
    await page.locator('.cp-settings-panel').screenshot({ path: info.outputPath(`highlight-status-${width}.png`) })
    await page.locator('[data-setting="work_preferences"]').click()
    const mode = page.getByRole('checkbox', { name: 'Remote', exact: true })
    await mode.focus()
    await expect(mode.locator('..')).toHaveCSS('outline-style', 'none')
    await page.locator('.cp-settings-panel').screenshot({ path: info.outputPath(`work-mode-${width}.png`) })
    await page.locator('[data-setting="work_preferences"]').click()
  }
})

test('custom choices edit inline and save without extra buttons', async ({ page }, info) => {
  let saved = structuredClone(profile)
  let patches = 0
  await page.route('**/api/v1/**', route => {
    if (route.request().url().endsWith('/auth/me/')) return route.fulfill({ json: { id: 9001, full_name: profile.full_name, email: profile.email, role: 'candidate' } })
    if (route.request().method() === 'PATCH') {
      patches++
      saved = { ...saved, career_preferences: { ...saved.career_preferences, ...route.request().postDataJSON().career_preferences } }
    }
    return route.fulfill({ json: saved })
  })
  await page.goto('/')
  await page.getByRole('button', { name: "That's me ✓" }).click()
  await page.getByRole('button', { name: '+ Add my own', exact: true }).first().click()
  const input = page.getByRole('textbox', { name: 'Your own motivation' })
  await expect(input).toBeFocused()
  await expect(page.getByRole('button', { name: 'Add option', exact: true })).toHaveCount(0)
  await input.fill('Meaningful impact')
  await input.press('Enter')
  await expect(page.getByRole('button', { name: 'Meaningful impact', exact: true })).toHaveAttribute('aria-pressed', 'true')
  await page.getByRole('button', { name: '+ Add my own', exact: true }).first().click()
  await input.fill('Flexible schedule')
  await input.press('Tab')
  await expect(page.getByRole('button', { name: 'Flexible schedule', exact: true })).toHaveAttribute('aria-pressed', 'true')
  const beforeCancel = patches
  await page.getByRole('button', { name: '+ Add my own', exact: true }).first().click()
  await input.fill('Cancelled choice')
  await input.press('Escape')
  await expect(input).toHaveCount(0)
  expect(patches).toBe(beforeCancel)
  for (const width of [1440, 390]) {
    await page.setViewportSize({ width, height: 900 })
    await page.getByRole('button', { name: '+ Add my own', exact: true }).first().click()
    await input.fill('Type here')
    await page.locator('.cp-beyond').screenshot({ path: info.outputPath(`inline-choice-${width}.png`) })
    expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(width)
    await input.press('Escape')
  }
  await page.reload()
  await page.getByRole('button', { name: "That's me ✓" }).click()
  await expect(page.getByRole('button', { name: 'Meaningful impact', exact: true })).toHaveAttribute('aria-pressed', 'true')
})

async function capture(page: Page, info: TestInfo, name: string) {
  await page.evaluate(() => document.fonts.ready)
  if (await page.locator('.platform-background video').count()) {
    await expect(page.locator('.platform-background')).toHaveAttribute('data-media-ready', 'true')
  }
  await page.screenshot({ path: info.outputPath(`${name}.png`), fullPage: false, animations: 'disabled' })
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
}

test('candidate confirmation reference screenshots', async ({ page }, info) => {
  let savedProfile = structuredClone(profile)
  let submissions = 0
  await page.route('**/api/v1/**', route => {
    const path = new URL(route.request().url()).pathname
    if (path.endsWith('/auth/me/')) return route.fulfill({ json: { id: 9001, full_name: profile.full_name, email: profile.email, role: 'candidate' } })
    if (path.endsWith('/candidate/profile/submit/')) {
      submissions++
      savedProfile = { ...savedProfile, profile_status: 'submitted', submission_consent_at: '2026-10-16T00:00:00Z' }
    }
    return route.fulfill({ json: savedProfile })
  })
  await page.goto('/')
  await page.getByRole('button', { name: 'Confirm my profile', exact: true }).click()
  await page.getByLabel('I agree to share my profile', { exact: false }).check()
  await expect(page.getByRole('button', { name: "Yes, that's me ✓", exact: true })).toHaveCSS('background-color', 'rgb(48, 56, 66)')
  await page.locator('.cp-brief').screenshot({ path: info.outputPath('review-charcoal.png') })
  await page.getByRole('button', { name: "Yes, that's me ✓", exact: true }).click()
  await expect(page.getByRole('heading', { name: "You're in.", exact: true })).toBeVisible()
  await expect(page.getByRole('button', { name: 'View my profile' })).toHaveCSS('background-color', 'rgb(48, 56, 66)')
  const viewProfile = page.getByRole('button', { name: 'View my profile' })
  await viewProfile.hover()
  await expect(viewProfile).toHaveCSS('background-color', 'rgb(48, 56, 66)')
  await expect(viewProfile).toHaveCSS('color', 'rgb(255, 255, 255)')
  await viewProfile.focus()
  await expect(viewProfile).toHaveCSS('background-color', 'rgb(48, 56, 66)')
  await page.mouse.down()
  await expect(viewProfile).toHaveCSS('color', 'rgb(255, 255, 255)')
  await page.mouse.move(0, 0)
  await page.mouse.up()
  await expect(page.getByRole('complementary', { name: 'Career Settings panel' })).toHaveCount(0)
  for (const width of [1440, 1024, 768, 390]) {
    await page.setViewportSize({ width, height: 900 })
    await page.evaluate(() => window.scrollTo(0, 0))
    await capture(page, info, `success-${width}`)
    const bounds = (await page.locator('.cp-success').boundingBox())!
    expect(Math.abs(bounds.x + bounds.width / 2 - width / 2)).toBeLessThan(3)
  }
  await page.emulateMedia({ reducedMotion: 'reduce' })
  expect(await page.locator('.cp-success').evaluate(el => el.getAnimations({ subtree: true }).length)).toBe(0)
  await expect(page.locator('.cp-confirmation-content')).toHaveCSS('opacity', '1')
  await page.reload()
  await expect(page.locator('.cp-identity')).toContainText(profile.full_name)
  await expect(page.getByRole('complementary', { name: 'Career Settings panel' })).toBeVisible()
  expect(savedProfile.profile_status).toBe('submitted')
  expect(submissions).toBe(1)
})

test('batch one: same-screen candidate and landing visual review', async ({ page }, info) => {
  test.setTimeout(90_000)
  await page.addInitScript(() => sessionStorage.removeItem('enter-door-intro-seen'))
  let signedIn = false
  let upload = false
  let visualProfile = structuredClone(profile)
  visualProfile.career_preferences = { ...visualProfile.career_preferences, likely_directions: ['AI Engineering Leadership'] }
  await page.route('**/api/v1/**', route => {
    const url = new URL(route.request().url())
    if (url.pathname.endsWith('/auth/me/')) return route.fulfill({ status: signedIn ? 200 : 401, json: signedIn ? { id: 9001, full_name: profile.full_name, email: profile.email, role: 'candidate' } : { detail: 'Not signed in' } })
    if (url.pathname.endsWith('/candidate/profile/')) {
      if (route.request().method() === 'PATCH') {
        const patch = route.request().postDataJSON()
        visualProfile = { ...visualProfile, ...patch, career_preferences: { ...visualProfile.career_preferences, ...patch.career_preferences } }
      }
      return route.fulfill({ json: upload ? { ...visualProfile, latest_resume: null } : visualProfile })
    }
    return route.fulfill({ json: {} })
  })
  for (const width of [1440, 1024, 768, 390]) {
    await page.setViewportSize({ width, height: 1000 })
    signedIn = false
    await page.goto('/')
    await expect(page.locator('.ce-mountain-hero')).toBeVisible()
    await expect(page.locator('.enter-intro-shell')).toHaveCount(0)
    await expect(page.locator('.career-edition')).toHaveCSS('--enter-primary', '#303842')
    await capture(page, info, `landing-${width}`)
    await page.getByTestId('for-candidates').click()
    await expect(page.getByRole('button', { name: 'Create account', exact: true })).toBeVisible()
    await expect(page.getByRole('button', { name: 'Create account', exact: true })).toHaveCSS('background-color', 'rgb(48, 56, 66)')
    await capture(page, info, `signup-${width}`)
    await page.goto('/recruiter')
    await expect(page.getByRole('button', { name: 'Log in', exact: true })).toBeVisible()
    await expect(page.getByRole('button', { name: 'Log in', exact: true })).toHaveCSS('background-color', 'rgb(48, 56, 66)')
    await capture(page, info, `recruiter-${width}`)
    signedIn = true
    upload = true
    await page.goto('/')
    await expect(page.getByRole('heading', { name: 'Start with your resume' })).toBeVisible()
    await expect(page.locator('.onboarding-choose')).toHaveCSS('background-color', 'rgb(48, 56, 66)')
    await capture(page, info, `upload-${width}`)
    upload = false
    await page.reload()
    await expect(page.locator('.cp-identity')).toContainText(profile.full_name)
    const identity = (await page.locator('.cp-identity-card').boundingBox())!
    const settings = (await page.locator('.cp-settings').boundingBox())!
    if (width >= 1024) {
      expect(Math.abs(identity.y - settings.y)).toBeLessThan(1)
      expect(settings.width).toBe(320)
      expect(identity.width).toBe(width === 1440 ? 778 : 642)
    } else {
      const main = (await page.locator('.cp-profile-main').boundingBox())!
      expect(settings.y).toBeGreaterThanOrEqual(main.y + main.height)
    }
    await expect(page.getByRole('button', { name: 'Confirm my profile', exact: true })).toHaveCSS('background-color', 'rgb(48, 56, 66)')
    await page.getByRole('button', { name: "That's me ✓" }).click()
    // Let the existing Beyond-the-CV focus/scroll finish before the full-page
    // capture, otherwise the sticky header can be captured mid-scroll.
    await page.evaluate(() => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve))))
    await page.evaluate(() => window.scrollTo({ top: 0, behavior: 'instant' }))
    await expect.poll(() => page.evaluate(() => scrollY)).toBe(0)
    const initialSource = await page.locator('.platform-background video').getAttribute('src')
    await page.evaluate(() => window.scrollTo(0, document.body.scrollHeight))
    expect((await page.locator('.platform-background').boundingBox())?.y).toBe(0)
    await expect(page.locator('.platform-background video')).toHaveAttribute('src', initialSource!)
    await page.evaluate(() => window.scrollTo({ top: 0, behavior: 'instant' }))
    await capture(page, info, `profile-${width}`)
    await page.locator('.cp-settings-panel').screenshot({ path: info.outputPath(`settings-detail-${width}.png`) })
    await page.locator('.cp-skills').screenshot({ path: info.outputPath(`skills-detail-${width}.png`) })
    await page.locator('.cp-spectrum').screenshot({ path: info.outputPath(`spectrum-detail-${width}.png`) })
    await page.mouse.move(0, 0)
    const spectrumHeading = page.locator('.cp-spectrum h3')
    await expect(page.locator('.cp-spectrum-markers span')).toHaveCount(5)
    await expect(page.locator('.cp-spectrum > div > p')).toHaveCount(0)
    await expect(page.locator('.cp-spectrum-labels span')).toHaveCount(5)
    for (const name of ['Exceptional team', 'Pure management']) {
      const chip = page.getByRole('button', { name, exact: true })
      if (await chip.getAttribute('aria-pressed') !== 'true') await chip.click()
      await chip.hover()
      await expect(chip).toHaveCSS('background-color', 'rgb(11, 115, 120)')
      await expect(chip).toHaveCSS('border-top-color', 'rgb(11, 115, 120)')
      await expect(chip).toHaveCSS('color', 'rgb(255, 255, 255)')
    }
    const answer = page.getByRole('textbox', { name: "What is the most meaningful thing you've built?" })
    expect((await answer.boundingBox())!.height).toBeGreaterThanOrEqual(32)
    expect((await answer.boundingBox())!.height).toBeLessThanOrEqual(60)
    await page.locator('.cp-beyond').screenshot({ path: info.outputPath(`beyond-selected-${width}.png`) })
    await expect(page.getByRole('slider', { name: 'Build and Lead preference' })).toHaveCSS('border-top-width', '0px')
    await expect(page.getByRole('slider', { name: 'Build and Lead preference' })).toHaveCSS('height', '44px')
    await expect(spectrumHeading).toHaveCSS('font-weight', '600')
    await expect(spectrumHeading).toHaveText('Build ↔ Lead Spectrum')
    for (const label of ['Notice period', 'Compensation', 'Work preferences']) {
      const typography = await page.locator('.cp-setting-row strong').filter({ hasText: label }).evaluate(el => {
        const s = getComputedStyle(el)
        return { 'font-size': s.fontSize, 'font-weight': s.fontWeight, 'line-height': s.lineHeight, color: s.color }
      })
      for (const [property, value] of Object.entries(typography)) await expect(spectrumHeading).toHaveCSS(property, value)
    }
    const skillChips = page.locator('.cp-skill-chips span')
    await expect(page.locator('.cp-setting-resume')).toContainText('Update your resume')
    await expect(page.locator('.cp-setting-resume')).toContainText('Last uploaded 1 Oct 2026')
    await expect(page.getByRole('heading', { name: "ENTER's read on you", exact: true })).toBeVisible()
    await expect(page.locator('.cp-read-wordmark image')).toHaveAttribute('href', '/enter-wordmark.svg')
    await expect(page.locator('.cp-read-heading > :first-child')).toHaveClass(/cp-read-sparkle/)
    for (const chips of [skillChips, page.locator('.cp-highlight-topics span')]) {
      await expect(chips.first()).toHaveCSS('background-color', 'rgb(11, 115, 120)')
      await expect(chips.first()).toHaveCSS('color', 'rgb(255, 255, 255)')
    }
    for (const panel of ['.cp-professional-read', '.cp-highlight']) {
      await expect(page.locator(panel)).toHaveCSS('background-color', 'rgba(229, 246, 243, 0.93)')
    }
    await expect(page.locator('.cp-likely')).toHaveCount(0)
    await expect(skillChips).toHaveText(profile.skills)
    await expect(skillChips.first()).toHaveCSS('font-size', '11px')
    await expect(skillChips.first()).toHaveCSS('padding', '3px 8px')
    await expect(skillChips.first()).toHaveCSS('min-height', '24px')
    // A constrained long label must wrap inside the chip, not widen its card.
    await skillChips.last().evaluate(el => { el.style.maxWidth = '60px' })
    expect(await skillChips.last().evaluate(el => el.scrollWidth <= el.clientWidth)).toBe(true)
    await skillChips.last().evaluate(el => { el.style.removeProperty('max-width') })
    await page.getByRole('button', { name: /Notice period.*Edit/ }).click()
    await expect(page.locator('.cp-settings-inline-editor')).toHaveCSS('background-color', 'rgba(0, 0, 0, 0)')
    await expect(page.locator('.cp-setting-resume .cp-replace-control')).toHaveCSS('background-color', 'rgba(229, 246, 243, 0.93)')
    const thatsMe = page.locator('.cp-profile-confirm button.primary')
    await expect(thatsMe).toHaveCSS('background-color', 'rgb(48, 56, 66)')
    await expect(thatsMe).toHaveCSS('border-top-color', 'rgb(48, 56, 66)')
    await expect(page.locator('.cp-setting-edit').first()).toHaveCSS('color', 'rgb(48, 56, 66)')
    await page.locator('.cp-settings-inline-editor select').focus()
    await expect(page.locator('.cp-settings-inline-editor select')).toHaveCSS('outline-color', 'rgb(48, 56, 66)')
    await capture(page, info, `settings-edit-${width}`)
    await page.locator('.cp-welcome').click()
    await expect(page.locator('.cp-settings-inline-editor')).toHaveCount(0)
    await page.getByRole('button', { name: /Compensation.*Edit/ }).click()
    await expect(page.getByLabel('Current CTC (₹ LPA)')).toHaveValue('20')
    await expect(page.getByLabel('Expected CTC (₹ LPA)')).toHaveValue('30')
    await expect(page.getByLabel('Current CTC (₹ LPA)')).toHaveCSS('appearance', 'textfield')
    await page.locator('.cp-settings-panel').screenshot({ path: info.outputPath(`compensation-${width}.png`) })
    await page.locator('.cp-welcome').click()
    await expect(page.locator('.cp-settings-inline-editor')).toHaveCount(0)
    for (const field of ['availability', 'notice_period_days', 'current', 'work_preferences', 'email', 'linkedin']) {
      await page.locator(`[data-setting="${field}"]`).click()
      const editor = page.locator('.cp-settings-inline-editor')
      await expect(editor.locator('fieldset').first()).toHaveCSS('margin-top', '0px')
      await expect(editor.locator('.cp-autosave-status')).toHaveCSS('line-height', '14px')
      if (width === 390) {
        for (const input of await editor.locator('input:not([type=hidden]):not([type=checkbox]):not([type=radio]), select').all()) {
          expect((await input.boundingBox())!.height).toBeGreaterThanOrEqual(44)
        }
      }
      for (const choice of await editor.locator('.cp-choice').all()) {
        await expect(choice).toHaveCSS('min-height', '24px')
        await expect(choice).toHaveCSS('padding', '3px 8px')
        await expect(choice).toHaveCSS('font-size', '11px')
      }
      if (field === 'availability') {
        await expect(editor.getByRole('group', { name: 'Job Search Status' })).toBeVisible()
        await expect(editor.getByRole('radio')).toHaveCount(3)
        await expect(editor.getByRole('combobox')).toHaveCount(0)
      }
      if (field === 'work_preferences') {
        await expect(editor.getByRole('group', { name: 'Work mode' })).toBeVisible()
        await expect(editor.locator('select[name=setup]')).toHaveCount(0)
        const location = editor.getByRole('combobox', { name: 'Preferred locations' })
        await location.focus()
        await expect(location).toHaveCSS('outline-offset', '-2px')
        await expect(location).toHaveCSS('box-shadow', 'none')
      }
      await editor.screenshot({ path: info.outputPath(`compact-${field}-${width}.png`) })
      await page.locator('.cp-welcome').click()
      await expect(editor).toHaveCount(0)
    }
    await page.getByRole('button', { name: /Engineer at Sample Labs/ }).focus()
    await expect(page.getByRole('tooltip')).toBeVisible()
    await expect(page.getByRole('tooltip')).toHaveCSS('--enter-primary', '#303842')
    await capture(page, info, `timeline-${width}`)
    await page.locator('.cp-career').screenshot({ path: info.outputPath(`journey-detail-${width}.png`) })
    await expect(page.locator('.career-laptop')).toHaveCount(2)
    await expect(page.locator('.career-laptop').first()).toHaveCSS('width', '12px')
    await expect(page.locator('.career-laptop').first()).toHaveCSS('color', 'rgb(11, 115, 120)')
    await expect(page.locator('.career-laptop').first()).toHaveAttribute('stroke-width', '1.75')
    await expect(page.locator('.career-period small')).toHaveText(['2018', '2020'])
    const markerBox = (await page.locator('.career-marker-icon').first().boundingBox())!
    const dateBox = (await page.locator('.career-period small').first().boundingBox())!
    expect(dateBox.y).toBeGreaterThan(markerBox.y + markerBox.height)
    expect(dateBox.y - markerBox.y - markerBox.height).toBeLessThanOrEqual(4)
  }
})

test('batch three autosave: rapid edits, errors, validation, navigation and locations', async ({ page }, info) => {
  test.setTimeout(90_000)
  let saved = structuredClone(profile)
  saved.career_preferences.preferred_locations = ['Bengaluru', 'Custom Valley']
  let fail = false
  let hold: Promise<void> | undefined
  let release!: () => void
  const patches: Record<string, unknown>[] = []
  let concurrent = 0
  let maxConcurrent = 0
  await page.route('**/api/v1/**', async route => {
    const url = new URL(route.request().url())
    if (url.pathname.endsWith('/auth/me/')) return route.fulfill({ json: { id: 9001, full_name: saved.full_name, email: saved.email, role: 'candidate' } })
    if (url.pathname.endsWith('/candidate/profile/')) {
      if (route.request().method() === 'PATCH') {
        concurrent++; maxConcurrent = Math.max(maxConcurrent, concurrent)
        const patch = route.request().postDataJSON()
        patches.push(patch)
        if (hold) await hold
        concurrent--
        if (fail) return route.fulfill({ status: 400, json: { detail: 'Please check your entered values.' } })
        saved = { ...saved, ...patch, career_preferences: { ...saved.career_preferences, ...patch.career_preferences } }
      }
      return route.fulfill({ json: saved })
    }
    return route.fulfill({ json: {} })
  })
  await page.goto('/')
  const status = page.locator('.cp-autosave-status')
  const editor = page.locator('.cp-settings-inline-editor')
  await page.getByRole('button', { name: /Notice period.*Edit/ }).click()
  fail = true
  await page.getByRole('combobox', { name: 'Notice period' }).selectOption('45')
  await expect(editor.getByRole('alert')).toContainText('entries are kept')
  await expect(page.getByRole('combobox', { name: 'Notice period' })).toHaveValue('45')
  await page.getByRole('button', { name: /Compensation.*Edit/ }).click()
  await expect(page.getByRole('combobox', { name: 'Notice period' })).toHaveValue('45')
  fail = false
  await editor.getByRole('button', { name: 'Retry' }).click()
  await expect(status).toHaveText('Saved')
  await expect(editor).toHaveCount(0)
  await expect(page.locator('[data-setting="notice_period_days"]')).toBeFocused()
  await expect(editor.getByRole('button', { name: /^(Save|Update|Cancel)$/ })).toHaveCount(0)
  await page.locator('.cp-welcome').click()
  await expect(editor).toHaveCount(0)
  await page.reload()
  await expect(page.getByRole('button', { name: /Notice period.*45 days.*Edit/ })).toBeVisible()

  await page.getByRole('button', { name: /Compensation.*Edit/ }).click()
  await page.getByLabel('Current CTC (₹ LPA)').fill('20.5')
  await expect(status).toHaveText('Saved')
  await expect(editor).toHaveCount(1)
  await page.getByLabel('Expected CTC (₹ LPA)').fill('30')
  await page.locator('.cp-welcome').click()
  await expect(editor).toHaveCount(0)
  await page.reload()
  await page.getByRole('button', { name: /Compensation.*Edit/ }).click()
  await expect(page.getByLabel('Current CTC (₹ LPA)')).toHaveValue('20.5')
  await expect(page.getByLabel('Expected CTC (₹ LPA)')).toHaveValue('30')
  hold = new Promise(resolve => { release = resolve })
  await page.getByLabel('Current CTC (₹ LPA)').fill('21')
  await expect(status).toHaveText('Saving…')
  await page.getByLabel('Current CTC (₹ LPA)').fill('23')
  await page.getByLabel('Expected CTC (₹ LPA)').fill('33')
  await page.getByRole('button', { name: /Work preferences.*Edit/ }).click()
  await expect(page.getByLabel('Current CTC (₹ LPA)')).toHaveValue('23')
  hold = undefined; release()
  const combo = page.getByRole('combobox', { name: 'Preferred locations' })
  await expect(combo).toBeVisible()
  expect(saved.current_salary_lpa).toBe('23')
  expect(saved.expected_salary_lpa).toBe('33')
  expect(maxConcurrent).toBe(1)

  await combo.fill('mum')
  await combo.press('Enter')
  await expect(status).toHaveText('Saved')
  await combo.fill('Remote Europe')
  await combo.press('Enter')
  await expect(status).toHaveText('Saved')
  await combo.fill(' MUMBAI ')
  await combo.press('Enter')
  await expect(page.getByRole('button', { name: 'Remove Mumbai', exact: true })).toHaveCount(1)
  await page.getByRole('checkbox', { name: 'Remote', exact: true }).check()
  await expect(status).toHaveText('Saved')
  expect(saved.work_preferences).toEqual(['Hybrid', 'Remote'])
  await page.getByRole('checkbox', { name: 'On-site', exact: true }).check()
  await expect(status).toHaveText('Saved')
  await page.getByRole('checkbox', { name: 'On-site', exact: true }).uncheck()
  await expect(status).toHaveText('Saved')
  expect(saved.work_preferences).toEqual(['Hybrid', 'Remote'])
  expect(saved.career_preferences.preferred_locations).toEqual(['Bengaluru', 'Custom Valley', 'Mumbai', 'Remote Europe'])
  for (const width of [1440, 1024, 768, 390]) {
    await page.setViewportSize({ width, height: 1000 })
    await combo.focus()
    await page.evaluate(() => window.scrollTo({ top: 0, behavior: 'instant' }))
    await page.screenshot({ path: info.outputPath(`autosave-locations-${width}.png`), fullPage: true })
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
  }
  await page.getByRole('button', { name: /How should we reach you.*Edit/ }).click()
  await page.getByRole('combobox', { name: 'Contact preference' }).selectOption('WhatsApp')
  await expect(status).toHaveText('Saved')
  await page.getByLabel('Phone', { exact: true }).fill('+919876543210')
  await expect(status).toHaveText('Saved')
  await page.getByRole('button', { name: /Professional links.*Edit/ }).click()
  const count = patches.length
  await page.getByLabel('LinkedIn', { exact: true }).fill('https://')
  await expect(status).toContainText('Complete valid values')
  expect(patches).toHaveLength(count)
  await page.locator('.cp-welcome').click()
  await expect(page.getByLabel('LinkedIn', { exact: true })).toHaveValue('https://')
  await page.getByLabel('LinkedIn', { exact: true }).fill('https://www.linkedin.com/in/fictional-test')
  await expect(status).toHaveText('Saved')
  await page.getByLabel('GitHub', { exact: true }).fill('https://github.com/example')
  await expect(status).toHaveText('Saved')
  await page.getByLabel('Portfolio', { exact: true }).fill('https://example.com/portfolio')
  await expect(status).toHaveText('Saved')
  await editor.screenshot({ path: info.outputPath('separate-professional-links.png') })
  await page.getByRole('button', { name: /Job Search Status.*Edit/ }).click()
  await page.getByRole('radio', { name: 'Actively Looking', exact: true }).check()
  await expect(status).toHaveText('Saved')
  await expect(editor).toHaveCount(0)
  await page.reload()
  await expect(page.getByRole('button', { name: /Job Search Status.*Actively Looking.*Edit/ })).toBeVisible()
  await expect(page.getByRole('button', { name: /Work preferences.*Remote Europe.*Edit/ })).toBeVisible()
  expect(saved.linkedin_url).toBe('https://www.linkedin.com/in/fictional-test')
  expect(saved.github_url).toBe('https://github.com/example')
  expect(saved.career_preferences.portfolio_url).toBe('https://example.com/portfolio')
  await page.getByRole('button', { name: /Work preferences.*Edit/ }).click()
  await expect(page.getByRole('checkbox', { name: 'Hybrid', exact: true })).toBeChecked()
  await expect(page.getByRole('checkbox', { name: 'Remote', exact: true })).toBeChecked()
  await page.getByRole('button', { name: /Professional links.*Edit/ }).click()
  await expect(page.getByLabel('GitHub', { exact: true })).toHaveValue('https://github.com/example')
  await expect(page.getByLabel('Portfolio', { exact: true })).toHaveValue('https://example.com/portfolio')
  expect(saved.phone).toBe('+919876543210')
  expect(saved.career_preferences.contact_preferences).toEqual(['WhatsApp'])

  // A successful single-choice save is acknowledged before the gentle close;
  // editing again during that acknowledgement must keep the latest choice.
  await page.setViewportSize({ width: 1440, height: 1000 })
  await page.getByRole('button', { name: /Job Search Status.*Edit/ }).click()
  const availability = (name: string) => page.getByRole('radio', { name, exact: true })
  await availability('Not Looking').check()
  await expect(editor.getByRole('status')).toHaveText('Saved')
  await availability('Not Looking').press('ArrowLeft')
  await expect(availability('Open to Opportunities')).toBeChecked()
  await expect(editor.getByRole('status')).toHaveText('Saved')
  await page.waitForFunction(() => document.querySelector('.cp-settings-inline-editor')?.getAnimations().some(animation => animation.playState === 'running' && (animation.effect as KeyframeEffect).getKeyframes().at(-1)?.height === '0px'))
  await expect(editor).toHaveCount(0)
  expect(saved.career_preferences.availability).toBe('Open to the right opportunity')
  await expect(page.locator('[data-setting="availability"]')).toBeFocused()
  await page.locator('.cp-settings-panel').screenshot({ path: info.outputPath('settings-closed-1440.png') })

  await page.emulateMedia({ reducedMotion: 'reduce' })
  await page.setViewportSize({ width: 390, height: 1000 })
  await page.getByRole('button', { name: /Job Search Status.*Edit/ }).click()
  expect(await editor.evaluate(form => form.getAnimations().length)).toBe(0)
  await availability('Actively Looking').check()
  await expect(editor).toHaveCount(0)
  await expect(page.locator('[data-setting="availability"]')).toBeFocused()
  await page.locator('.cp-settings-panel').screenshot({ path: info.outputPath('settings-closed-390.png') })
  expect(saved.career_preferences.availability).toBe('Actively looking')
})
