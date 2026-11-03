import { useEffect } from 'react'
import './site-motion.css'

/** Enhance newly mounted public content without delaying its availability. */
export default function SiteMotion() {
  useEffect(() => {
    const preference = window.matchMedia('(prefers-reduced-motion: reduce)')
    if (typeof IntersectionObserver !== 'function' || !Element.prototype.animate) return
    const seen = new WeakSet<Element>()
    const active = new Set<Animation>()
    let observer: IntersectionObserver
    try { observer = new IntersectionObserver(entries => {
      for (const entry of entries) {
        if (!entry.isIntersecting) continue
        observer.unobserve(entry.target)
        if (preference.matches) continue
        const animation = entry.target.animate(
          [{ opacity: .3, transform: 'translateY(12px)' }, { opacity: 1, transform: 'translateY(0)' }],
          { duration: 480, easing: 'cubic-bezier(.22,1,.36,1)' },
        )
        active.add(animation)
        animation.onfinish = () => active.delete(animation)
      }
    }, { threshold: .08 }) } catch { return }
    const scan = () => {
      document.querySelectorAll('.opp-hero, .opp-row, .opp-discover, .opp-next, .careers-hero, .careers-role-row').forEach(element => {
        if (seen.has(element)) return
        seen.add(element)
        observer.observe(element)
      })
    }
    let frame = 0
    const mutations = new MutationObserver(() => {
      if (!frame) frame = requestAnimationFrame(() => { frame = 0; scan() })
    })
    mutations.observe(document.getElementById('root')!, { childList: true, subtree: true })
    const cancel = () => { if (preference.matches) active.forEach(animation => animation.cancel()) }
    preference.addEventListener('change', cancel)
    scan()
    return () => { mutations.disconnect(); observer.disconnect(); cancelAnimationFrame(frame); active.forEach(animation => animation.cancel()); preference.removeEventListener('change', cancel) }
  }, [])
  return null
}
