import { expect, test } from '@playwright/test'

test.use({ hasTouch: true })

for (const width of [390, 768, 1440]) for (const state of ['incomplete', 'no-employment'] as const) {
  test(`${state} Career Journey stays concise at ${width}px`, async ({ page }) => {
    await page.setViewportSize({ width, height: 900 })
    await page.emulateMedia({ reducedMotion: 'reduce' })
    await page.route('**/career-ux-state*', route => route.fulfill({ contentType: 'text/html; charset=utf-8', body: `
      <html><head><meta charset="utf-8"><style>body{margin:0;background:#eaf0ee}*{box-sizing:border-box}</style></head><body><div id="review"></div><script type="module">
      import React from '/node_modules/.vite/deps/react.js';
      import ReactDOM from '/node_modules/.vite/deps/react-dom_client.js';
      import RefreshRuntime from '/@react-refresh';
      import '/src/styles.css'; import '/src/components/candidate-experience.css'; import '/src/components/candidate-theme.css';
      RefreshRuntime.injectIntoGlobalHook(window);window.$RefreshReg$=()=>{};window.$RefreshSig$=()=>type=>type;window.__vite_plugin_react_preamble_installed__=true;
      const {default:Timeline}=await import('/src/components/CandidateCareerTimeline.tsx');
      const state=new URLSearchParams(location.search).get('state');
      const items=state==='incomplete'?Array.from({length:5},(_,i)=>({id:i+1,company:'Fictional Employer '+(i+1),role:'Engineer '+(i+1),start_date:String(2010+i*3)+'-03-01',end_date:String(2011+i*3)+'-08-01',date_label:'Mar '+(2010+i*3)+' — Aug '+(2011+i*3),confidence_status:'supported',employment_type:'Full-time',description:'',gap_reason:''})):[];
      const extraction={resume_id:4,status:state==='incomplete'?'review_required':'confirmed_no_employment',source:'rules',accepted_role_count:0,saved_role_count:items.length,verified_role_ids:[],unverified_role_ids:items.map(item=>item.id),profile_state:'previous_history_preserved',stale_profile_preserved:state==='incomplete'};
      ReactDOM.createRoot(document.getElementById('review')).render(React.createElement('main',{className:'candidate-experience',style:{maxWidth:1000,margin:'24px auto',padding:'0 16px'}},React.createElement('section',{className:'cp-career-surface'},React.createElement(Timeline,{items,extraction,edit:()=>{}}))));
      </script></body></html>` }))
    await page.goto(`/career-ux-state?state=${state}`)
    const card = page.locator('.cp-career-surface')
    await expect(card.getByRole('heading', { name: 'Your career journey' })).toBeVisible()
    await expect(card.getByText('Tap or hover over a marker to view your role.')).toBeVisible()
    await expect(card.locator('.career-history-status')).toHaveCount(1)
    if (state === 'incomplete') {
      const graph = card.getByRole('list', { name: 'Career journey' })
      await expect(graph.locator('.career-sequence')).toHaveCount(5)
      await expect(card.getByText('5 saved roles · Tap a marker for details')).toBeVisible()
      await expect(card.getByRole('status')).toHaveText('Latest resume could not be fully read; saved roles remain visible.')
      await expect(card.getByRole('button', { name: 'Fix dates' })).toHaveCount(0)
      const graphBox = (await graph.boundingBox())!
      const noticeBox = (await card.getByRole('status').boundingBox())!
      expect(noticeBox.y).toBeGreaterThanOrEqual(graphBox.y + graphBox.height)
      const marker = graph.locator('.career-period .career-job').first()
      await marker.tap()
      await expect(page.getByRole((await marker.getAttribute('aria-haspopup')) === 'dialog' ? 'dialog' : 'tooltip')).toContainText('Not matched to the latest resume.')
      await page.keyboard.press('Escape')
      await page.evaluate(() => (document.activeElement as HTMLElement | null)?.blur())
    } else {
      await expect(card.getByRole('list', { name: 'Career journey' })).toHaveCount(0)
      await expect(card.getByRole('status')).toHaveText('No jobs were listed in this resume.')
      await expect(card.getByRole('button', { name: 'Add a role' })).toBeVisible()
      await expect(card).not.toContainText(/fresher/i)
    }
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1)).toBe(true)
    if (width !== 768) await card.screenshot({ path: `test-results/career-${state}-${width}.png`, animations: 'disabled' })
  })
}
