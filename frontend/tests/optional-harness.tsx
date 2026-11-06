import { useEffect, useState } from 'react'
import { createRoot } from 'react-dom/client'
import { createPortal } from 'react-dom'
import App from '../src/App'
import IntroAnimation from '../src/components/IntroAnimation'
import MountainHero from '../src/components/MountainHero'
import '../src/styles.css'
import '../src/components/platform-background.css'
import '../src/components/platform-glass.css'

export function Harness() {
  const [hero, setHero] = useState<Element | null>(null)
  useEffect(() => {
    const observer = new MutationObserver(() => setHero(document.querySelector('.ce-mountain-hero')))
    observer.observe(document.getElementById('root')!, { childList: true, subtree: true })
    return () => observer.disconnect()
  }, [])
  return document.getElementById('root')?.dataset.component === 'intro'
    ? <IntroAnimation><App /></IntroAnimation>
    : <><App />{hero && createPortal(<MountainHero />, hero)}</>
}

createRoot(document.getElementById('root')!).render(<Harness />)
