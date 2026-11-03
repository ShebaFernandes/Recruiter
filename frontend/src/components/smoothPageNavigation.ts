import type { MouseEvent } from 'react'
import { flushSync } from 'react-dom'

export function navigateSmoothly(event: MouseEvent<HTMLAnchorElement>) {
  if (event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return
  event.preventDefault()
  const destination = event.currentTarget.pathname
  navigateToPage(destination)
}

export function navigateToPage(destination: string) {
  const update = () => {
    flushSync(() => {
      window.history.pushState({}, '', destination)
      window.dispatchEvent(new PopStateEvent('popstate'))
    })
    window.scrollTo({ top: 0, behavior: 'instant' })
  }
  if (document.startViewTransition && !window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
    document.startViewTransition(update)
  } else {
    update()
  }
}
