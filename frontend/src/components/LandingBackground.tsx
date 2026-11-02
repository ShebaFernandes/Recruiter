import { type ReactNode } from 'react'
import './landing-background.css'

const plates = ['sky', 'mountains-distant', 'mountains-middle', 'clouds-back', 'mountains-foreground', 'clouds-front']

/** Static artwork with CSS camera motion, not generated footage or the Apogee source. */
export default function LandingBackground({ children }: { children: ReactNode }) {
  return <div className="platform-surface landing-surface">
    <div className="landing-background" aria-hidden="true">
      <div className="landing-background__scene">
        {plates.map((plate, index) => <img key={plate} className={`landing-background__${plate}`} src={`/hero/mountain-v1/${plate}.webp`} alt="" width={1536} height={1024} draggable={false} decoding="async" fetchPriority={index === 0 ? 'high' : 'auto'} />)}
      </div>
    </div>
    <div className="platform-content">{children}</div>
  </div>
}
