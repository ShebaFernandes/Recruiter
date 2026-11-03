import observeLandingReveal from './observeLandingReveal'
import { useEffect, useRef } from 'react'
import { flushSync } from 'react-dom'
import './for-talent.css'


export default function ForTalent({ onJoin, onLogin }: { onJoin: () => void; onLogin: () => void }) {
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
        <h2 id="for-talent-title" >Join ambitious AI and <br />engineering teams.</h2>
        <p className="for-talent__description">enter connects talent with companies building what’s next. Browse open roles and apply directly, or tell us what you’re looking for.</p>
        <div className="for-talent__tracks">{['AI and ML', 'Engineering', 'Product', 'Leadership'].map(track => <span key={track}>{track}</span>)}</div>
        <a className="for-talent__browse" href="/opportunities" onClick={event => {
          if (event.metaKey || event.ctrlKey || event.shiftKey || event.altKey || event.button !== 0) return
          event.preventDefault()
          transitionTo(() => {
            window.history.pushState({}, '', '/opportunities')
            window.dispatchEvent(new PopStateEvent('popstate'))
          })
        }}>Browse open roles</a>
        <p className="for-talent__hint for-talent__availability"><span aria-hidden="true" /><span><strong>50+ roles open now.</strong> Find one that fits and apply directly.</span></p>
      </div>

      <aside className="for-talent__network" aria-labelledby="talent-network-title">

        <h3 id="talent-network-title">Don’t see your role?</h3>
        <p>Log in to join enter’s talent network. Add your CV and the work you want, and we’ll reach out when a relevant role opens.</p>
        <button type="button" onClick={() => transitionTo(onLogin)}>Join enter’s Talent network</button>
        <p className="for-talent__hint">New to enter? <button type="button" className="for-talent__signup" onClick={() => transitionTo(onJoin)}>Create an account</button> to get started.</p>
      </aside>
    </div>
  </section>
}
