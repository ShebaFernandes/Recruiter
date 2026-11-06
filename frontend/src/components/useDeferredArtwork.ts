import { useEffect, useState, type RefObject } from 'react'

/** Observe the actual image, with one readiness transition and an eager error fallback. */
export default function useDeferredArtwork(target: RefObject<HTMLElement | null>, enabled = true) {
  const [ready, setReady] = useState(() => !enabled || typeof IntersectionObserver !== 'function')
  useEffect(() => {
    if (!enabled || !target.current || typeof IntersectionObserver !== 'function') return
    let observer: IntersectionObserver | undefined
    try {
      observer = new IntersectionObserver(entries => {
        if (entries.some(entry => entry.isIntersecting)) {
          setReady(true)
          observer?.disconnect()
        }
      }, { rootMargin: '600px' })
      observer.observe(target.current)
    } catch {
      // Unsupported/broken observation must never leave artwork without a source.
      const timer = window.setTimeout(() => setReady(true), 0)
      return () => { window.clearTimeout(timer); observer?.disconnect() }
    }
    return () => observer?.disconnect()
  }, [target, enabled])
  return ready
}
