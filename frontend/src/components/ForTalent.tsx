import observeLandingReveal from './observeLandingReveal'
import { useEffect, useRef } from 'react'
import { flushSync } from 'react-dom'
import './for-talent.css'


export default function ForTalent({ onJoin }: { onJoin: () => void }) {
  const sectionRef = useRef<HTMLElement>(null)
  const navigating = useRef(false)
  function transitionTo(action: () => void) {
    if (navigating.current) return
    navigating.current = true
    const update = () => { flushSync(action); window.scrollTo({ top: 0, behavior: 'instant' }) }
    if (document.startViewTransition && !window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
      void document.startViewTransition(update).finished.finally(() => { navigating.current = false })
    } else {
      update()
      navigating.current = false
    }
  }

  useEffect(() => {
    const section = sectionRef.current
    if (section) return observeLandingReveal(section, 0.2)
  }, [])

  return <section ref={sectionRef} className="for-talent" aria-labelledby="for-talent-title">
    <div className="for-talent__inner">
      <div className="for-talent__content">
        <p className="for-talent__eyebrow">FOR TALENT</p>
        <h2 id="for-talent-title" aria-label="Let's find work that feels great.">Let's find work that<br />feels great.</h2>
        <p className="for-talent__description">Find opportunities with ambitious companies building what's next.</p>
        <p className="for-talent__category-line">AI &amp; ML · ENGINEERING · PRODUCT · LEADERSHIP</p>
        <a className="for-talent__browse" href="/opportunities" onClick={event => {
          if (event.metaKey || event.ctrlKey || event.shiftKey || event.altKey || event.button !== 0) return
          event.preventDefault()
          transitionTo(() => {
            window.history.pushState({}, '', '/opportunities')
            window.dispatchEvent(new PopStateEvent('popstate'))
          })
        }}>Explore open opportunities <span aria-hidden="true">→</span></a>
        <p className="for-talent__hint">Find a role that fits and apply directly.</p>
      </div>

      <aside className="for-talent__network" aria-labelledby="talent-network-title">
        <p className="for-talent__network-label">FOR FUTURE OPPORTUNITIES</p>
        <h3 id="talent-network-title">Don’t see your role?</h3>
        <p>Join enter’s talent network and share your CV, experience, and the work you’re looking for.</p>
        <button type="button" onClick={() => transitionTo(onJoin)}>Join enter’s talent network</button>
        <p className="for-talent__hint">We’ll reach out when a relevant opportunity comes up.</p>
      </aside>
    </div>
  </section>
}
