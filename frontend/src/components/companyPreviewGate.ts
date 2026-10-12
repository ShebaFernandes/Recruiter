/** Local design review only. This is not a public feature flag or permission grant. */
export function isCompanyPreviewAllowed(dev: boolean, hostname: string, search: string) {
  return dev && ['localhost', '127.0.0.1', '[::1]'].includes(hostname)
    && new URLSearchParams(search).get('preview') === 'company-logos'
}
