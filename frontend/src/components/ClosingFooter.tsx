import { artwork } from '../assets/landing/artwork'
import ResponsiveArtwork from './ResponsiveArtwork'
import { navigateSmoothly } from './smoothPageNavigation'
import { warmPublicPage } from '../publicPageLoader'
import EnterLogo from './EnterLogo'
import observeLandingReveal from './observeLandingReveal'
import { useEffect, useRef } from 'react'
import './closing-footer.css'

const companyLinks = [
  { label: 'Hire Talent', href: '#what-building-title', tab: 'hire' },
  { label: 'Build a Team', href: '#what-building-title', tab: 'team' },
  { label: 'Recruitment Drives', href: '#what-building-title', tab: 'drive' },
] as const

export default function ClosingFooter({ onCandidate, onJoinNetwork = onCandidate }: { onCandidate: () => void; onJoinNetwork?: () => void }) {
  const sectionRef = useRef<HTMLElement>(null)

  useEffect(() => {
    const section = sectionRef.current
    if (section) return observeLandingReveal(section, 0.22)
  }, [])

  return <section ref={sectionRef} id="closing-section" className="closing-section" aria-label="Build with enter">
    <div className="closing-cta" aria-labelledby="closing-cta-title">
      <ResponsiveArtwork className="closing-cta__landscape" artwork={artwork.closing} sizes="(max-width: 1400px) 1400px, 100vw" alt="" aria-hidden="true" />
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
          <button type="button" onClick={onJoinNetwork}>Join enter's Talent network</button>
          <a href="/opportunities" onPointerEnter={() => warmPublicPage('/opportunities')} onFocus={() => warmPublicPage('/opportunities')} onClick={navigateSmoothly}>Opportunities</a>
        </nav>

        <nav className="enter-footer__column" aria-label="enter">
          <h3>ENTER</h3>
          <a href="#talent-principles">About</a>
          <a href="/careers" onPointerEnter={() => warmPublicPage('/careers')} onFocus={() => warmPublicPage('/careers')} onClick={navigateSmoothly}>Careers</a>
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
