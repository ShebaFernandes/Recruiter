import { expect, test } from '@playwright/test'

test.use({ hasTouch:true })
for (const width of [390, 1440]) test(`internship-to-job reference layout at ${width}px`, async ({ page }, info) => {
  await page.setViewportSize({ width, height:900 })
  await page.emulateMedia({ reducedMotion:'reduce' })
  await page.route('**/career-reference-review', route => route.fulfill({ contentType:'text/html; charset=utf-8', body:`
    <html><head><meta charset="utf-8"></head><body><div id="review"></div><script type="module">
    import React from '/node_modules/.vite/deps/react.js';
    import ReactDOM from '/node_modules/.vite/deps/react-dom_client.js';
    import RefreshRuntime from '/@react-refresh';
    import '/src/styles.css'; import '/src/components/candidate-experience.css'; import '/src/components/candidate-theme.css';
    RefreshRuntime.injectIntoGlobalHook(window);window.$RefreshReg$=()=>{};window.$RefreshSig$=()=>type=>type;window.__vite_plugin_react_preamble_installed__=true;
    const {default:Timeline}=await import('/src/components/CandidateCareerTimeline.tsx');
    const items=[
      {id:1,company:'Orchid Research and Technologies',role:'AI Intern / SDE Intern - AI',start_date:'2026-01-01',end_date:'2026-07-01',date_label:'Jan 2026 - Jul 2026',confidence_status:'supported',description:'Built reliable research tools.',gap_reason:''},
      {id:2,company:'Cedar Recruitment',role:'AI Full-Stack Developer',start_date:'2026-09-01',end_date:null,is_current:true,date_label:'Sep 2026 - Present',confidence_status:'supported',description:'Built reliable recruiting tools.',gap_reason:''}
    ];
    const extraction={resume_id:2,status:'verified_fallback',source:'rules',accepted_role_count:2,saved_role_count:2,verified_role_ids:[1,2],unverified_role_ids:[],candidate_confirmed_role_ids:[],stale_profile_preserved:false,profile_state:'applied'};
    ReactDOM.createRoot(document.getElementById('review')).render(React.createElement('main',{className:'candidate-experience',style:{padding:24,maxWidth:1200,margin:'auto'}},React.createElement('div',{className:'cp-career-surface'},React.createElement(Timeline,{items,extraction}))));
    </script></body></html>` }))
  await page.goto('/career-reference-review')
  const graph = page.getByRole('list', { name:'Career journey' })
  const summaries = graph.locator('.career-role-summary')
  await expect(summaries).toHaveCount(2)
  await expect(summaries.nth(0)).toContainText('Orchid Research and Technologies')
  await expect(summaries.nth(0)).toContainText('AI Intern / SDE Intern - AI')
  await expect(summaries.nth(0)).toContainText('Jan 2026 — Jul 2026')
  await expect(summaries.nth(1)).toContainText('Sep 2026 — Present')
  await expect(graph.locator('.career-period small')).toHaveText(['2026','2026'])
  await expect(graph.locator('.career-end-year')).toHaveCSS('white-space','nowrap')
  await expect(graph.locator('.is-internship .career-period-line')).toHaveCSS('background-color','rgb(143, 199, 196)')
  await expect(graph.locator('.career-sequence:not(.is-internship)>.career-period-line')).toHaveCSS('background-color','rgb(11, 115, 120)')
  await expect(graph.locator('.career-axis')).toHaveClass(/is-current/)
  await expect(graph.locator('.career-gap-period')).toHaveCount(1)
  const internship = await graph.locator('.is-internship>.career-period-line').boundingBox()
  const gap = await graph.locator('.career-gap-period').boundingBox()
  const next = await graph.locator('.career-sequence:not(.is-internship)>.career-period-line').boundingBox()
  expect(internship!.x + internship!.width).toBeCloseTo(gap!.x, 0)
  expect(gap!.x + gap!.width).toBeCloseTo(next!.x, 0)
  const first = await summaries.nth(0).boundingBox(), second = await summaries.nth(1).boundingBox()
  expect(first!.x + first!.width).toBeLessThanOrEqual(second!.x)
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true)
  await page.locator('.cp-career-surface').screenshot({ path:info.outputPath(`reference-${width}.png`) })
  const marker = graph.getByRole('button', { name:/AI Intern.* at Orchid/ })
  if (width === 1440) await marker.hover(); else await marker.tap()
  await expect(page.getByRole('tooltip')).toContainText('Internship')
  await expect(page.getByRole('tooltip')).toContainText('Built reliable research tools.')
  await page.keyboard.press('Escape')
  await graph.getByRole('button', { name:/AI Full-Stack Developer at/ }).focus()
  await expect(page.getByRole('tooltip')).toContainText('Sep 2026 — Present')
  await page.keyboard.press('Escape')
  await graph.getByRole('button', { name:/Career gap/ }).focus()
  await expect(page.getByRole('tooltip')).toContainText('Approximately 1 month')
})
