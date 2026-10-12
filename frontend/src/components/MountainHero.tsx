import { useEffect, useRef } from 'react'

const layers = [
  ['sky', 'sky'],
  ['distant', 'mountains-distant'],
  ['middle', 'mountains-middle'],
  ['clouds-back', 'clouds-back'],
  ['foreground', 'mountains-foreground'],
  ['clouds-front', 'clouds-front'],
] as const

/** Decorative only: content and navigation never depend on motion support. */
export default function MountainHero() {
  const scene = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const element = scene.current
    const hero = element?.parentElement
    if (!element || !hero || typeof window.matchMedia !== 'function') return
    const reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)')
    const mobile = window.matchMedia('(max-width: 760px)')
    let visible = false
    let frame = 0
    let observer: IntersectionObserver | undefined
    const reset = () => {
      for (const depth of ['distant', 'middle', 'foreground']) {
        element.style.setProperty(`--ce-${depth}-offset`, '0px')
      }
      element.style.setProperty('--ce-scene-opacity', '1')
    }
    const update = () => {
      frame = 0
      if (!visible || document.hidden || reducedMotion.matches || mobile.matches) return
      const { top, height } = hero.getBoundingClientRect()
      const progress = Math.min(1, Math.max(0, -top / height))
      // Reveal depth early in the scroll, then settle without a hard stop.
      // The nearest ridge stays inside the 10% overscan, even at full scroll.
      const depth = 1 - (1 - progress) ** 3
      element.style.setProperty('--ce-distant-offset', `${height * 0.02 * depth}px`)
      element.style.setProperty('--ce-middle-offset', `${height * 0.05 * depth}px`)
      element.style.setProperty('--ce-foreground-offset', `${height * 0.08 * depth}px`)
      element.style.setProperty('--ce-scene-opacity', String(1 - 0.22 * progress))
    }
    const schedule = () => {
      if (!frame && visible && !document.hidden && !reducedMotion.matches && !mobile.matches) {
        frame = window.requestAnimationFrame(update)
      }
    }
    const syncMotion = () => {
      element.dataset.active = String(visible && !document.hidden && !reducedMotion.matches)
      window.cancelAnimationFrame(frame)
      frame = 0
      if (reducedMotion.matches || mobile.matches) reset()
      else schedule()
    }
    try {
      if (typeof window.IntersectionObserver === 'function') {
        observer = new IntersectionObserver(entries => {
          visible = entries.some(entry => entry.isIntersecting)
          syncMotion()
        })
        observer.observe(hero)
      }
    } catch {
      // Static scenery remains visible if observation is unavailable or fails.
      observer?.disconnect()
    }
    window.addEventListener('scroll', schedule, { passive: true })
    window.addEventListener('resize', schedule)
    document.addEventListener('visibilitychange', syncMotion)
    reducedMotion.addEventListener('change', syncMotion)
    mobile.addEventListener('change', syncMotion)
    return () => {
      observer?.disconnect()
      window.cancelAnimationFrame(frame)
      window.removeEventListener('scroll', schedule)
      window.removeEventListener('resize', schedule)
      document.removeEventListener('visibilitychange', syncMotion)
      reducedMotion.removeEventListener('change', syncMotion)
      mobile.removeEventListener('change', syncMotion)
    }
  }, [])

  return <div className="ce-mountain-scene" ref={scene} aria-hidden="true" data-active="false">
    <div className="ce-landscape-canvas">
      {layers.map(([depth, file]) => <img key={depth}
        className={`ce-landscape-layer ce-landscape-${depth}`}
        src={`/hero/mountain-v1/${file}.webp`} alt="" width={1536} height={1024}
        decoding="async" draggable={false} />)}
    </div>
    <svg className="ce-landscape-curves" viewBox="0 0 1440 800" preserveAspectRatio="xMidYMid slice" focusable="false">
      <path d="M-80 560 C100 565 175 510 235 445" />
      <path d="M1380 440 C1280 250 1370 155 1520 180" />
      <circle className="ce-curve-node ce-curve-node-left" r="3" />
      <circle className="ce-curve-node ce-curve-node-right" r="3" />
    </svg>
  </div>
}
