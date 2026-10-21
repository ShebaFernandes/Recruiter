import { useCallback, useEffect, useLayoutEffect, useRef, useState, type ReactNode } from 'react'
import './intro-animation.css'
import { portalLighting } from './portalLighting'

const sessionKey = 'enter-door-intro-seen'
let seenWithoutStorage = false
const phase = (progress: number, from: number, to: number) => {
  const value = Math.max(0, Math.min(1, (progress - from) / (to - from)))
  return value * value * (3 - 2 * value)
}
function shouldPlay() {
  if (typeof window === 'undefined' || window.location.pathname !== '/' || !window.matchMedia || window.matchMedia('(prefers-reduced-motion: reduce)').matches) return false
  if (import.meta.env.DEV && new URLSearchParams(window.location.search).get('intro') === 'replay') return true
  try { return sessionStorage.getItem(sessionKey) !== '1' && !seenWithoutStorage } catch { return false }
}

/** One short automatic entrance; never intercept scrolling or lock the body. */
export default function IntroAnimation({ children }: { children: ReactNode }) {
  const [active, setActive] = useState(shouldPlay)
  const shellRef = useRef<HTMLDivElement>(null)
  const sceneRef = useRef<HTMLElement>(null)
  const contentRef = useRef<HTMLDivElement>(null)
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const doorRef = useRef<HTMLDivElement>(null)
  const completion = useRef<{ focus: boolean; scroll: number } | null>(null)
  const finished = useRef(false)
  const finish = useCallback((remainingScroll = 0) => {
    if (finished.current) return
    finished.current = true
    completion.current = { focus: document.activeElement === document.body || !!sceneRef.current?.contains(document.activeElement), scroll: remainingScroll }
    setActive(false)
  }, [])

  useLayoutEffect(() => {
    if (active || !completion.current) return
    const { focus, scroll } = completion.current
    // Remove completed intro travel when the fixed preview becomes normal content.
    window.scrollTo({ top: scroll, behavior: 'instant' })
    if (focus) contentRef.current?.querySelector<HTMLElement>('#enter-home')?.focus({ preventScroll: true })
    completion.current = null
  }, [active])

  useEffect(() => {
    if (!active) return
    seenWithoutStorage = true
    try { sessionStorage.setItem(sessionKey, '1') } catch { /* In-memory replay guard. */ }
    sceneRef.current?.focus({ preventScroll: true })
    let frame: number | undefined
    let lighting: ReturnType<typeof portalLighting> = null
    try {
      if (canvasRef.current && sceneRef.current && doorRef.current) lighting = portalLighting(canvasRef.current, sceneRef.current, doorRef.current)
    } catch { /* CSS lighting remains available without canvas. */ }
    const started = performance.now()
    const render = (now: number) => {
      frame = undefined
      const shell = shellRef.current
      if (!shell) { finish(); return }
      const progress = Math.min(1, (now - started) / 4400)
      const open = phase(progress, .14, .52)
      const approach = phase(progress, .40, .84)
      const reveal = phase(progress, .85, 1)
      const depth = 1078 * approach
      shell.style.setProperty('--intro-rotation', `${102 * open}deg`)
      shell.style.setProperty('--intro-depth', `${depth}px`)
      shell.style.setProperty('--intro-light', `${phase(progress, .14, .32)}`)
      shell.style.setProperty('--intro-wash', `${phase(progress, .72, .84)}`)
      shell.style.setProperty('--intro-reveal', `${reveal}`)
      shell.style.setProperty('--intro-scene', `${1 - reveal}`)
      try { lighting?.draw(open, depth) } catch { lighting?.dispose(); lighting = null }
      shell.dataset.progress = progress.toFixed(4)
      if (progress >= 1) finish()
      else frame = requestAnimationFrame(render)
    }
    const motion = window.matchMedia('(prefers-reduced-motion: reduce)')
    const onMotion = () => { if (motion.matches) finish() }
    const onVisibility = () => { if (document.hidden) finish() }
    document.addEventListener('visibilitychange', onVisibility)
    motion.addEventListener('change', onMotion)
    // Fail open if rendering stalls or the tab is backgrounded.
    const watchdog = window.setTimeout(() => finish(), 5500)
    frame = requestAnimationFrame(render)
    return () => {
      if (frame !== undefined) cancelAnimationFrame(frame)
      clearTimeout(watchdog)
      lighting?.dispose()
      document.removeEventListener('visibilitychange', onVisibility)
      motion.removeEventListener('change', onMotion)
    }
  }, [active, finish])

  return <div ref={shellRef} className={`enter-intro-shell${active ? ' is-active' : ''}`}>
    <div ref={contentRef} inert={active} className="enter-intro-content">{children}</div>
    {active && <div className="enter-intro-track">
      <section ref={sceneRef} className="enter-intro" tabIndex={-1} aria-label="Welcome to ENTER" onKeyDown={event => { if (event.key === 'Escape') finish() }}>
        <div className="enter-intro-room" aria-hidden="true">
          <div className="enter-intro-floor" />
          <canvas ref={canvasRef} className="enter-intro-bloom" />
          <div className="enter-intro-camera"><div ref={doorRef} className="enter-intro-frame">
            <div className="enter-intro-light" />
            <div className="enter-intro-leaf">
              <span className="enter-intro-panel" /><span className="enter-intro-panel" /><span className="enter-intro-panel" /><span className="enter-intro-panel" />
              <span className="enter-intro-handle" />
            </div>
          </div></div>
        </div>
        <div className="enter-intro-wash" aria-hidden="true" />
        <button type="button" className="enter-intro-skip" onClick={() => finish()}>Skip intro <span aria-hidden="true">→</span></button>
      </section>
    </div>}
  </div>
}
