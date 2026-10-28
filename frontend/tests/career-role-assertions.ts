import { expect, type Locator, type Page } from '@playwright/test'

export type ExpectedCareerRole = readonly [company: string, title: string, dates?: string]

async function settleTimeline(page: Page) {
  await page.evaluate(async () => {
    await document.fonts.ready
    await new Promise<void>(resolve => requestAnimationFrame(() => resolve()))
    await new Promise<void>(resolve => requestAnimationFrame(() => resolve()))
  })
}

/** Count saved roles, including members of accessible marker clusters. */
export async function expectDiscoverableCareerRoles(
  page: Page,
  timeline: Locator,
  expected: readonly ExpectedCareerRole[],
) {
  await settleTimeline(page)
  const markers = timeline.locator('.career-period > .career-job')
  await expect(markers.first()).toBeVisible()
  // Layout is measured after the card renders. Wait for grouping to settle
  // before enumerating markers, including the roles hidden inside clusters.
  let previousCount = -1
  let stableSamples = 0
  await expect.poll(async () => {
    const counts = await markers.evaluateAll(buttons => buttons.map(button =>
      Number(button.querySelector('.career-cluster-count')?.textContent) || 1,
    ))
    const total = counts.reduce((sum, count) => sum + count, 0)
    stableSamples = total === expected.length && counts.length === previousCount ? stableSamples + 1 : 0
    previousCount = counts.length
    return stableSamples >= 3 ? total : -1
  }, { intervals: [100] }).toBe(expected.length)
  const markerCount = await markers.count()
  const details: string[] = []
  for (let index = 0; index < markerCount; index += 1) {
    const marker = markers.nth(index)
    await marker.scrollIntoViewIfNeeded({ timeout: 5000 })
    await marker.click()
    if (await marker.getAttribute('aria-haspopup') === 'dialog') {
      const dialog = page.getByRole('dialog', { name: /roles grouped here/ })
      await expect(dialog).toBeVisible()
      const roles = dialog.locator('li')
      const grouped = Number(await marker.locator('.career-cluster-count').textContent())
      expect(grouped).toBeGreaterThan(1)
      await expect(roles).toHaveCount(grouped)
      details.push(...await roles.allTextContents())
      await dialog.getByRole('button', { name: 'Close role list' }).click()
    } else {
      const tooltip = page.getByRole('tooltip')
      await expect(tooltip).toBeVisible()
      details.push(await tooltip.innerText())
      await dismissCareerPopover(timeline)
    }
  }
  expect(details).toHaveLength(expected.length)
  const unmatched = [...details]
  for (const [company, title, dates] of expected) {
    const normalizedDates = dates?.replace(' - ', ' — ')
    const match = unmatched.findIndex(text =>
      text.includes(company) && text.includes(title) && (!normalizedDates || text.includes(normalizedDates)),
    )
    expect(match, `Discoverable saved role: ${company}, ${title}, ${normalizedDates}`).toBeGreaterThanOrEqual(0)
    unmatched.splice(match, 1)
  }
}

export async function openCareerRole(page: Page, timeline: Locator, company: string, title: string) {
  await settleTimeline(page)
  const markers = timeline.locator('.career-period > .career-job')
  for (let index = 0; index < await markers.count(); index += 1) {
    const marker = markers.nth(index)
    await marker.scrollIntoViewIfNeeded()
    await marker.click()
    if (await marker.getAttribute('aria-haspopup') === 'dialog') {
      const dialog = page.getByRole('dialog', { name: /roles grouped here/ })
      const role = dialog.locator('li').filter({ hasText: company }).filter({ hasText: title })
      if (await role.count()) return role
      await dialog.getByRole('button', { name: 'Close role list' }).click()
    } else {
      const tooltip = page.getByRole('tooltip')
      const text = await tooltip.innerText()
      if (text.includes(company) && text.includes(title)) return tooltip
      await dismissCareerPopover(timeline)
    }
  }
  throw new Error(`Saved career role is not discoverable: ${company}, ${title}`)
}

export async function dismissCareerPopover(timeline: Locator) {
  // Escape belongs to the parent recruiter profile dialog and would close it.
  await timeline.locator('..').locator('.career-legend').click()
}
