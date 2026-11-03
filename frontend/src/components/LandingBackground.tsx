import { useEffect, useState, type ReactNode } from 'react'
import { Pause, Play } from 'lucide-react'
import './landing-background.css'

const plates = ['sky', 'mountains-distant', 'mountains-middle', 'clouds-back', 'mountains-foreground', 'clouds-front']

/** Static artwork with CSS camera motion, not generated footage or the Apogee source. */
export default function LandingBackground({ children }: { children: ReactNode }) {
  const [paused, setPaused] = useState(false)
  const [reduced, setReduced] = useState(() => window.matchMedia?.('(prefers-reduced-motion: reduce)').matches ?? true)
  const [hidden, setHidden] = useState(document.hidden)
  useEffect(() => {
    const preference = window.matchMedia?.('(prefers-reduced-motion: reduce)')
    const motion = () => setReduced(preference?.matches ?? true)
    const visibility = () => setHidden(document.hidden)
    preference?.addEventListener('change', motion)
    document.addEventListener('visibilitychange', visibility)
    return () => { preference?.removeEventListener('change', motion); document.removeEventListener('visibilitychange', visibility) }
  }, [])
  return <div className="platform-surface landing-surface" data-motion-paused={paused || hidden || reduced}>
    <div className="landing-background" aria-hidden="true">
      <div className="landing-background__scene">
        {plates.map((plate, index) => <img key={plate} className={`landing-background__${plate}`} src={`/hero/mountain-v1/${plate}.webp`} alt="" width={1536} height={1024} draggable={false} decoding="async" fetchPriority={index === 0 ? 'high' : 'auto'} />)}
      </div>
    </div>
    <div className="platform-content">{children}</div>
    {!reduced && <button type="button" className="landing-motion-toggle" aria-label={paused ? 'Play background animation' : 'Pause background animation'} onClick={() => setPaused(value => !value)}>{paused ? <Play size={15} aria-hidden="true" /> : <Pause size={15} aria-hidden="true" />}</button>}
  </div>
}
