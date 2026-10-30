export type HiringTab = 'hire' | 'team'

type HiringNavigationState = { tab: HiringTab; role?: string }

const navigationEvent = 'enter:hiring-section-navigation'

export function navigateToHiringSection(tab: HiringTab, role?: string) {
  const detail: HiringNavigationState = { tab, role }
  const state = { ...window.history.state, enterHiring: detail }
  window.history.pushState(state, '', '#what-building-title')
  window.dispatchEvent(new CustomEvent<HiringNavigationState>(navigationEvent, { detail }))

  const reducedMotion = window.matchMedia?.('(prefers-reduced-motion: reduce)').matches ?? false
  document.getElementById('what-building-title')?.scrollIntoView({
    behavior: reducedMotion ? 'instant' : 'smooth',
    block: 'start',
  })
}

export function listenForHiringSectionNavigation(onNavigate: (detail: HiringNavigationState) => void) {
  const onEvent = (event: Event) => onNavigate((event as CustomEvent<HiringNavigationState>).detail)
  const onPopState = (event: PopStateEvent) => {
    const detail = event.state?.enterHiring as HiringNavigationState | undefined
    if (detail) onNavigate(detail)
  }
  window.addEventListener(navigationEvent, onEvent)
  window.addEventListener('popstate', onPopState)
  return () => {
    window.removeEventListener(navigationEvent, onEvent)
    window.removeEventListener('popstate', onPopState)
  }
}
