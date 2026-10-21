import { useEffect, useRef, useState, type ReactNode } from 'react'
import { Pause, Play } from 'lucide-react'
// Unfiltered 0.5s frame of the video below, 960×540 JPEG (63,952 bytes).
// Inline so navigation never waits for a separate poster request. Source SHA256:
// a9a24321597eaedccb1f30bfda552e7526dab9912184a704e353b7cdf95885e0
import poster from './platform-poster.jpg?inline'

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
    const update = () => { setReady(false); setReduced(preference.matches) }
    preference.addEventListener('change', update)
    return () => preference.removeEventListener('change', update)
  }, [])
  useEffect(() => {
    const media = video.current
    if (!media) return
    let frame: number | undefined
    let active = true
    const reveal = () => {
      if (media.readyState < 2 || frame !== undefined) return
      if (typeof media.requestVideoFrameCallback === 'function') {
        frame = media.requestVideoFrameCallback(() => { if (active) setReady(true) })
      } else {
        // loadeddata guarantees a decoded current frame on older browsers.
        setReady(true)
      }
    }
    media.addEventListener('loadeddata', reveal)
    reveal()
    return () => {
      active = false
      media.removeEventListener('loadeddata', reveal)
      if (frame !== undefined) media.cancelVideoFrameCallback(frame)
    }
  }, [reduced, failed])
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
    <div className="platform-background" style={{ backgroundImage: `url("${poster}")` }} aria-hidden="true" data-media-ready={ready} data-render-state={reduced || failed ? 'fallback' : playing ? 'running' : 'paused'}>
      {!reduced && !failed && <video ref={video} poster={poster} src="https://d8j0ntlcm91z4.cloudfront.net/user_38xzZboKViGWJOttwIXH07lWA1P/hf_20260820_010308_b1636845-4c15-4ab6-b0c9-9a29bfb0c6e3.mp4" autoPlay muted loop playsInline preload="metadata" onPlaying={() => setPlaying(true)} onPause={() => setPlaying(false)} onError={() => setFailed(true)} />}
    </div>
    <div className="platform-content">{children}</div>
    {!reduced && !failed && <button type="button" className="platform-motion-toggle" aria-label={paused ? 'Play background animation' : 'Pause background animation'} onClick={() => setPaused(value => !value)}>{paused ? <Play aria-hidden="true" /> : <Pause aria-hidden="true" />}</button>}
  </div>
}
