import { useEffect } from 'react'

/** Animate visible content once, without hiding content before JavaScript is ready. */
export default function useLandingMotion() {
  useEffect(() => {
    const preference = window.matchMedia?.('(prefers-reduced-motion: reduce)')
    if (!preference || preference.matches || typeof IntersectionObserver !== 'function' || typeof Element.prototype.animate !== 'function') return
    const animations = new Set<Animation>()
    const observer = new IntersectionObserver(entries => {
      entries.forEach(entry => {
        if (!entry.isIntersecting) return
        observer.unobserve(entry.target)
        const animation = entry.target.animate([
          { opacity: .2, translate: '0 22px' },
          { opacity: 1, translate: '0 0' },
        ], { duration: 750, easing: 'cubic-bezier(.22,1,.36,1)', fill: 'none' })
        animations.add(animation)
        animation.onfinish = () => animations.delete(animation)
      })
    }, { threshold: .12, rootMargin: '0px 0px -24px 0px' })
    document.querySelectorAll('.simple-landing section h2, .simple-landing .growth-stage-card, .simple-landing .enter-footer__column').forEach(element => observer.observe(element))
    const stop = () => { observer.disconnect(); animations.forEach(animation => animation.cancel()); animations.clear() }
    const motionChanged = () => { if (preference.matches) stop() }
    preference.addEventListener('change', motionChanged)
    return () => { stop(); preference.removeEventListener('change', motionChanged) }
  }, [])
}
