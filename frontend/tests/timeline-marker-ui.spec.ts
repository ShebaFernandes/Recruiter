import { expect, test } from '@playwright/test'
test.use({ hasTouch:true })

// Isolated component fixture uses the production component and styles, with
// fictional data. No resume worker, database mutation or new application route.
for (const width of [390, 1440]) {
  test(`shared laptop markers retain focus and tap details at ${width}px`, async ({ page }, info) => {
    await page.setViewportSize({ width, height:900 })
    await page.route('**/timeline-review', route => route.fulfill({ contentType:'text/html', body:`
      <html><body><div id="review"></div><script type="module">
      import React from '/node_modules/.vite/deps/react.js';
      import ReactDOM from '/node_modules/.vite/deps/react-dom_client.js';
      import RefreshRuntime from '/@react-refresh';
      import '/src/styles.css';
      import '/src/components/candidate-experience.css';
      import '/src/components/candidate-theme.css';
      RefreshRuntime.injectIntoGlobalHook(window);
      window.$RefreshReg$=()=>{}; window.$RefreshSig$=()=>type=>type;
      window.__vite_plugin_react_preamble_installed__=true;
      const {default:Journey}=await import('/src/components/CareerJourney.tsx');
      const items=[{company:'Northstar Applied Research and Technology Cooperative',role:'Machine Learning Platform Engineering Intern',start_date:'2018-03-01',end_date:'2020-01-01',description:'Built reliable tools.',gap_reason:''},
      {company:'Northstar Applied Research and Technology Cooperative',role:'Lead Applied Intelligence Platform Engineer',start_date:'2020-04-01',end_date:null,is_current:true,description:'Led the platform team.',gap_reason:'Training break'}];
      ReactDOM.createRoot(document.getElementById('review')).render(React.createElement('main',{style:{padding:20}},
        React.createElement('h1',null,'Shared timeline visual test'),
        React.createElement('section',{className:'cp-career'},React.createElement('h2',null,'Candidate'),React.createElement(Journey,{items,minimal:true,profilePresentation:true,compactMarkers:true,candidateMilestones:true,presentAtEnd:true})),
        React.createElement('section',null,React.createElement('h2',null,'Recruiter'),React.createElement(Journey,{items,detailed:true}))));
      </script></body></html>` }))
    await page.goto('/timeline-review')
    await expect(page.locator('.career-laptop')).toHaveCount(4)
    await expect(page.locator('.cp-career .career-role-summary')).toHaveCount(2)
    const candidate = page.locator('.cp-career .career-journey')
    const summaries = candidate.locator('.career-role-summary')
    await expect(summaries.first()).toContainText('Northstar Applied Research and Technology Cooperative')
    await expect(summaries.first()).toContainText('Machine Learning Platform Engineering Intern')
    await expect(summaries.first()).toContainText('Mar 2018 — Jan 2020')
    await expect(summaries.first().locator('strong')).toHaveCSS('white-space', 'normal')
    await expect(summaries.first().locator('strong')).toHaveCSS('text-overflow', 'clip')
    const candidateBox = await candidate.boundingBox()
    const finalTimelineBox = await candidate.locator('.career-present-end').boundingBox()
    expect(candidateBox).not.toBeNull()
    expect(finalTimelineBox).not.toBeNull()
    if (width === 1440) expect(finalTimelineBox!.x + finalTimelineBox!.width).toBeGreaterThan(candidateBox!.x + candidateBox!.width - 24)
    for (const graph of await page.locator('.career-journey').all()) {
      const icon = graph.locator('.career-laptop').first()
      await expect(icon).toHaveCSS('width', '12px')
      await expect(icon).toHaveCSS('color', 'rgb(11, 115, 120)')
      await expect(icon).toHaveAttribute('aria-hidden', 'true')
      const button = graph.getByRole('button', { name:/Lead Applied Intelligence Platform Engineer at Northstar/ })
      await button.focus()
      await expect(page.getByRole('tooltip')).toContainText('Led the platform team.')
      await page.keyboard.press('Escape')
      await expect(page.getByRole('tooltip')).toHaveCount(0)
      await button.tap()
      await expect(page.getByRole('tooltip')).toBeVisible()
      await page.keyboard.press('Escape')
    }
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
    await page.screenshot({ path:info.outputPath(`shared-timeline-${width}.png`), fullPage:true })
  })
}
