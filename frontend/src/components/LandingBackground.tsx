import { useState, type ReactNode } from 'react'
import { Pause, Play } from 'lucide-react'
import './landing-background.css'

const plates = ['sky', 'mountains-distant', 'mountains-middle', 'clouds-back', 'mountains-foreground', 'clouds-front']

/** Static artwork with CSS camera motion, not generated footage or the Apogee source. */
export default function LandingBackground({ children }: { children: ReactNode }) {
  const [paused, setPaused] = useState(false)
  return <div className="platform-surface landing-surface" data-motion-paused={paused}>
    <div className="landing-background" aria-hidden="true">
      <div className="landing-background__scene">
        {plates.map((plate, index) => <img key={plate} className={`landing-background__${plate}`} src={`/hero/mountain-v1/${plate}.webp`} alt="" width={1536} height={1024} draggable={false} decoding="async" fetchPriority={index === 0 ? 'high' : 'auto'} />)}
      </div>
    </div>
    <div className="platform-content">{children}</div>
    <button type="button" className="platform-motion-toggle landing-motion-toggle" aria-label={paused ? 'Play background animation' : 'Pause background animation'} onClick={() => setPaused(value => !value)}>{paused ? <Play aria-hidden="true" /> : <Pause aria-hidden="true" />}</button>
  </div>
}
