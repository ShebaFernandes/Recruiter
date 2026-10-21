import { useEffect, useRef, useState, type ReactNode } from 'react'
import { Pause, Play } from 'lucide-react'

/** One decorative video per platform screen, never inside cards or dialogs. */
export default function PlatformBackground({ children }: { children: ReactNode }) {
  const video = useRef<HTMLVideoElement>(null)
  const [paused, setPaused] = useState(false)
  const [reduced, setReduced] = useState(() => window.matchMedia?.('(prefers-reduced-motion: reduce)').matches ?? true)
  const [failed, setFailed] = useState(false)
  const [playing, setPlaying] = useState(false)
  const [ready, setReady] = useState(false)
  useEffect(() => {
    const preference = window.matchMedia?.('(prefers-reduced-motion: reduce)')
    if (!preference) return
    const update = () => setReduced(preference.matches)
    preference.addEventListener('change', update)
    return () => preference.removeEventListener('change', update)
  }, [])
  useEffect(() => {
    const media = video.current
    if (!media) return
    let active = true
    const sync = () => {
      if (document.hidden || paused || reduced || failed) { media.pause(); return }
      void media.play().catch(() => { if (active) setFailed(true) })
    }
    sync()
    document.addEventListener('visibilitychange', sync)
    return () => { active = false; document.removeEventListener('visibilitychange', sync); media.pause() }
  }, [paused, reduced, failed])
  return <div className="platform-surface">
    <div className="platform-background" aria-hidden="true" data-media-ready={ready} data-render-state={reduced || failed ? 'fallback' : playing ? 'running' : 'paused'}>
      {!reduced && !failed && <video ref={video} src="https://d8j0ntlcm91z4.cloudfront.net/user_38xzZboKViGWJOttwIXH07lWA1P/hf_20260820_010308_b1636845-4c15-4ab6-b0c9-9a29bfb0c6e3.mp4" autoPlay muted loop playsInline preload="metadata" onTimeUpdate={event => { if (event.currentTarget.currentTime > 0.2) setReady(true) }} onPlaying={() => setPlaying(true)} onPause={() => setPlaying(false)} onError={() => setFailed(true)} />}
    </div>
    <div className="platform-content">{children}</div>
    {!reduced && !failed && <button type="button" className="platform-motion-toggle" aria-label={paused ? 'Play background animation' : 'Pause background animation'} onClick={() => setPaused(value => !value)}>{paused ? <Play aria-hidden="true" /> : <Pause aria-hidden="true" />}</button>}
  </div>
}
