const loaders = {
  '/careers': () => import('./components/Careers'),
  '/opportunities': () => import('./components/Opportunities'),
}

export function warmPublicPage(path: string) {
  const load = loaders[path as keyof typeof loaders]
  if (load) void load().catch(() => { /* Navigation can retry a failed prefetch. */ })
}

export const loadCareers = loaders['/careers']
export const loadOpportunities = loaders['/opportunities']
