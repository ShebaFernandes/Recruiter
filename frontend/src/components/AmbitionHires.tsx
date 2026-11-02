import observeLandingReveal from './observeLandingReveal'
import { useEffect, useRef } from 'react'
import './ambition-hires.css'

export const ambitionHireResults = [
  { role: 'Senior Backend Engineers', company: 'Zepto', hires: 4 },
  { role: 'React Native Engineers', company: 'CoinSwitch', hires: 7 },
  { role: 'Senior Software Engineers', company: 'CoinDCX', hires: 6 },
  { role: 'Senior and Staff Backend Engineers', company: 'MPL', hires: 9 },
  { role: 'Engineering Managers', company: 'MobiKwik', hires: 2 },
  { role: 'Senior Android Developers', company: 'Practo', hires: 4 },
] as const

export default function AmbitionHires() {
  const sectionRef = useRef<HTMLElement>(null)
  useEffect(() => {
    const section = sectionRef.current
    if (section) return observeLandingReveal(section, 0.16)
  }, [])

  useEffect(() => {
    const section = sectionRef.current
    if (!section) return
    let frame = 0
    const update = () => {
      frame = 0
      const rect = section.getBoundingClientRect()
      const progress = Math.min(1, Math.max(0, (window.innerHeight - rect.top) / (window.innerHeight + rect.height * 0.25)))
      section.style.setProperty('--ambition-darkness', String(progress * 0.85))
      const mix = (a: number[], b: number[]) => `rgb(${a.map((v, i) => Math.round(v + (b[i] - v) * progress)).join(',')})`
      section.style.setProperty('--ambition-heading', mix([23, 33, 59], [255, 255, 255]))
      section.style.setProperty('--ambition-eyebrow', mix([48, 70, 201], [190, 204, 255]))
    }
    const schedule = () => { if (!frame) frame = requestAnimationFrame(update) }
    update()
    window.addEventListener('scroll', schedule, { passive: true })
    window.addEventListener('resize', schedule)
    return () => { cancelAnimationFrame(frame); window.removeEventListener('scroll', schedule); window.removeEventListener('resize', schedule) }
  }, [])

  return <section ref={sectionRef} className="ambition-hires" aria-labelledby="ambition-hires-title">
    <img className="ambition-hires__landscape" src="/media/ambition-hires-mountain.jpg" alt="" aria-hidden="true" />
    <div className="ambition-hires__wash" aria-hidden="true" />

    <div className="ambition-hires__inner">
      <header className="ambition-hires__header">
        <p>BUILT WITH ENTER</p>
        <h2 id="ambition-hires-title">From ambition to hires.</h2>
      </header>

      <div className="ambition-hires__panel" aria-label="Hiring results shown in the reference design">
        <ul>
          {ambitionHireResults.map(result => <li key={`${result.role}-${result.company}`}>
            <p><strong>{result.role}</strong><span aria-hidden="true"> · </span><span>{result.company}</span></p>
            <div><i aria-hidden="true" /><strong>{result.hires}</strong> hired</div>
          </li>)}
        </ul>
      </div>

    </div>
  </section>
}
