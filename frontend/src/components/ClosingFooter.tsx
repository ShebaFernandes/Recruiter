import { flushSync } from 'react-dom'
import observeLandingReveal from './observeLandingReveal'
import { useEffect, useRef, useState } from 'react'
import EnterLogo from './EnterLogo'
import './closing-footer.css'

type PendingDestination = 'Company access' | 'Opportunities'

const companyLinks = [
  { label: 'Hire Talent', href: '#what-building-title', tab: 'hire' },
  { label: 'Build a Team', href: '#what-building-title', tab: 'team' },
  { label: 'Recruitment Drives', href: '#what-building-title', tab: 'drive' },
] as const

export default function ClosingFooter({ onCandidate }: { onCandidate: () => void }) {
  const sectionRef = useRef<HTMLElement>(null)
  const [pending, setPending] = useState<PendingDestination | null>(null)

  useEffect(() => {
    const section = sectionRef.current
    if (section) return observeLandingReveal(section, 0.22)
  }, [])

  useEffect(() => {
    if (!pending) return
    const dismiss = window.setTimeout(() => setPending(null), 4000)
    return () => window.clearTimeout(dismiss)
  }, [pending])

  const comingSoon = (destination: PendingDestination) => setPending(destination)

  return <section ref={sectionRef} id="closing-section" className="closing-section" aria-label="Build with enter">
    <div className="closing-cta" aria-labelledby="closing-cta-title">
      <div className="closing-cta__content">
        <p className="closing-cta__eyebrow">THE BEST TEAMS ARE BUILT BY ENTER.</p>
        <h2 id="closing-cta-title">Who are you building next?</h2>
        <div className="closing-cta__actions">
          <button type="button" onClick={() => {
            const reducedMotion = window.matchMedia?.('(prefers-reduced-motion: reduce)').matches ?? false
            window.history.pushState(window.history.state, '', '#enter-home')
            document.getElementById('enter-home')?.focus({ preventScroll: true })
            window.scrollTo({ top: 0, behavior: reducedMotion ? 'instant' : 'smooth' })
          }}>
            For Companies
          </button>
          <button type="button" onClick={onCandidate}>
            For Candidates
          </button>
        </div>
        <p id="closing-availability" className={`closing-cta__status${pending ? ' is-visible' : ''}`} role="status" aria-live="polite">
          {pending ? `${pending} is coming soon.` : 'Company access and unfinished destinations are coming soon.'}
        </p>
      </div>
    </div>

    <div className="enter-footer-surface">
    <footer className="enter-footer">
      <div className="enter-footer__grid">
        <a className="enter-footer__brand" href="#enter-home" aria-label="enter home">
          <EnterLogo className="enter-footer__brand-mark" decorative />
        </a>

        <nav className="enter-footer__column" aria-label="For companies">
          <h3>FOR COMPANIES</h3>
          {companyLinks.map(link => <a key={link.label} href={link.href} onClick={() => {
            if ('tab' in link) document.getElementById(`building-tab-${link.tab}`)?.click()
          }}>{link.label}</a>)}
          {['Build Your Founding Team', 'Find Leadership'].map(label => <button type="button" key={label} onClick={() => {
            const trigger = Array.from(document.querySelectorAll<HTMLButtonElement>('.growth-stages__grid .growth-stage-card__cta')).find(button => button.textContent?.trim() === label)
            trigger?.click()
          }}>{label}</button>)}
        </nav>

        <nav className="enter-footer__column" aria-label="For candidates">
          <h3>FOR CANDIDATES</h3>
          <button type="button" onClick={onCandidate}>Join enter's Talent network</button>
          <button type="button" title="Coming soon" onClick={() => comingSoon('Opportunities')}>Opportunities <span className="enter-footer__soon">Coming soon</span></button>
        </nav>

        <nav className="enter-footer__column" aria-label="enter">
          <h3>ENTER</h3>
          <a href="#talent-principles">About</a>
          <a href="/careers" onClick={event => {
            if (event.metaKey || event.ctrlKey || event.shiftKey || event.altKey || event.button !== 0) return
            event.preventDefault()
            const openCareers = () => {
              window.history.pushState({}, '', '/careers')
              flushSync(() => window.dispatchEvent(new PopStateEvent('popstate')))
              window.scrollTo({ top: 0, behavior: 'instant' })
              document.querySelector<HTMLElement>('.careers-hero h1')?.focus({ preventScroll: true })
            }
            if (document.startViewTransition && !window.matchMedia('(prefers-reduced-motion: reduce)').matches) document.startViewTransition(openCareers)
            else openCareers()
          }}>Careers</a>
          <a href="mailto:sheba@enterrecruitment.com">Contact</a>
          <a href="https://www.linkedin.com/company/enterrecruitment/posts/?feedView=all" target="_blank" rel="noopener noreferrer">LinkedIn</a>
        </nav>
      </div>

      <div className="enter-footer__legal">
        <span>© enter Recruitment Private Limited</span>
        <span>Humanity. Integrity. Possibility.</span>
        <nav aria-label="Legal and social links">
          <a href="/privacy" aria-label="Privacy">Privacy</a>
          <a href="/terms" aria-label="Terms">Terms</a>
        </nav>
      </div>
    </footer>
    </div>
  </section>
}
