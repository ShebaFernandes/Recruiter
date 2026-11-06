import type { Page } from '@playwright/test'

/** Exercise retained optional components without re-enabling them on the public site. */
export async function optionalComponentHarness(page: Page, component: 'intro' | 'mountain') {
  await page.route('**/*', async route => {
    const url = new URL(route.request().url())
    if (route.request().resourceType() !== 'document' || url.pathname !== '/') return route.fallback()
    await route.fulfill({ contentType: 'text/html', body: `<!doctype html><html><head><meta name="viewport" content="width=device-width, initial-scale=1" /></head><body><div id="root" data-component="${component}"></div><script type="module">
import RefreshRuntime from '/@react-refresh';
RefreshRuntime.injectIntoGlobalHook(window);window.$RefreshReg$=()=>{};window.$RefreshSig$=()=>type=>type;window.__vite_plugin_react_preamble_installed__=true;
await import('/tests/optional-harness.tsx');
</script></body></html>` })
  })
}
