import { artwork } from '../assets/landing/artwork'
import ResponsiveArtwork from './ResponsiveArtwork'
import { loadHiringDrawer } from './hiringDrawerLoader'
import { afterHomepageIntro } from '../homepageHydration'
import { useEffect, useRef, useState, type ReactNode } from 'react'
import './landing-background.css'

const plates = ['sky', 'mountains-distant', 'mountains-middle', 'clouds-back', 'mountains-foreground', 'clouds-front'] as const

/** Static artwork with CSS camera motion, not generated footage or the Apogee source. */
export default function LandingBackground({ children }: { children: ReactNode }) {
  const [reduced, setReduced] = useState(() => window.matchMedia?.('(prefers-reduced-motion: reduce)').matches ?? true)
  const surface = useRef<HTMLDivElement>(null)
  const [detailReady, setDetailReady] = useState(false)
  useEffect(() => {
    if (!surface.current) return
    let active = true
    void afterHomepageIntro(surface.current).then(() => { if (active) { setDetailReady(true); void loadHiringDrawer().catch(() => undefined) } })
    return () => { active = false }
  }, [])
  const [offscreen, setOffscreen] = useState(false)
  useEffect(() => {
    if (!surface.current || typeof IntersectionObserver !== 'function') return
    const observer = new IntersectionObserver(entries => setOffscreen(!entries.some(entry => entry.isIntersecting)))
    observer.observe(surface.current)
    return () => observer.disconnect()
  }, [])
  const [hidden, setHidden] = useState(document.hidden)
  useEffect(() => {
    const preference = window.matchMedia?.('(prefers-reduced-motion: reduce)')
    const motion = () => setReduced(preference?.matches ?? true)
    const visibility = () => setHidden(document.hidden)
    preference?.addEventListener('change', motion)
    document.addEventListener('visibilitychange', visibility)
    return () => { preference?.removeEventListener('change', motion); document.removeEventListener('visibilitychange', visibility) }
  }, [])
  return <div ref={surface} className="platform-surface landing-surface" data-motion-paused={hidden || reduced || offscreen}>
    <div className="landing-background" aria-hidden="true">
      <div className="landing-background__scene">
        {plates.map(plate => <ResponsiveArtwork key={plate} className={`landing-background__${plate}`} artwork={artwork[plate.replaceAll('-', '_') as keyof typeof artwork]} sizes="(max-width: 768px) 1200px, 100vw" eager introPreview detailReady={detailReady} alt="" draggable={false} />)}
      </div>
    </div>
    <div className="platform-content">{children}</div>
  </div>
}
