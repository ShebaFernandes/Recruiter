import DeferredArtwork from './DeferredArtwork'
import EnterLogo from './EnterLogo'
import useLandingMotion from './useLandingMotion'
import LandingBackground from './LandingBackground'
import CompanyLogoMarquee from './company-preview/CompanyLogoPreview'
import WhatAreYouBuilding from './WhatAreYouBuilding'
import BrandStatement from './BrandStatement'
import GrowthStages from './GrowthStages'
import TalentPrinciples from './TalentPrinciples'
import AmbitionHires from './AmbitionHires'
import WhenTeamsChange from './WhenTeamsChange'
import TestimonialsCarousel from './TestimonialsCarousel'
import ForTalent from './ForTalent'
import ClosingFooter from './ClosingFooter'
import { navigateToHiringSection } from './hiringSectionNavigation'
import './landing.css'
import './simple-landing.css'
import './landing-flow.css'

export default function Landing({ choose }: {
  choose: (role: 'recruiter' | 'candidate', mode?: 'signup' | 'login') => void
}) {
  useLandingMotion()
  // "For Candidates" entry points land on the in-page candidate pitch first,
  // where visitors can browse roles or sign in/up — not straight into the job list.
  const openCandidate = () => {
    const reducedMotion = window.matchMedia?.('(prefers-reduced-motion: reduce)').matches ?? false
    window.history.pushState(window.history.state, '', '#for-talent-title')
    document.getElementById('for-talent-title')?.scrollIntoView({
      behavior: reducedMotion ? 'instant' : 'smooth',
      block: 'start',
    })
  }

  return <main className="career-edition simple-landing"><LandingBackground>
    <a className="ce-skip" href="#enter-home">Skip to content</a>
    <div className="ce-mountain-hero">
    <header className="ce-masthead">
      <div className="ce-brand-lockup">
      <a className="ce-logo" href="#enter-home" aria-label="enter home"><EnterLogo className="ce-header-logo" decorative /></a>
      <span className="ce-masthead-note">Humanity. Integrity and Possibility.</span>
      </div>
      <nav aria-label="Main navigation">
        {import.meta.env.VITE_CANDIDATE_ONLY !== 'true' && <button className="ce-audience-link" data-testid="for-recruiters" onClick={() => choose('recruiter', 'login')}>For Recruiters</button>}
        <button className="ce-audience-link" data-testid="for-companies" onClick={() => navigateToHiringSection('hire')}>For Companies</button>
        <button className="ce-audience-link" data-testid="for-candidates" onClick={openCandidate}>For Candidates</button>
      </nav>
    </header>

    <section className="ce-intro ce-page-width" id="enter-home" tabIndex={-1} aria-labelledby="ce-title">
      <div className="ce-intro-grid">
        <h1 id="ce-title" aria-label="The best teams are built by enter.">The best teams are<br />built by <span className="ce-headline-brand" aria-hidden="true"><EnterLogo className="ce-headline-logo" decorative />.</span></h1>
        <div className="ce-intro-aside">
          <p className="ce-supporting-headline">What You Build Tomorrow Depends on Who You Hire Today</p>
          <p>Every breakthrough product, high-performing team, and successful company is built by exceptional people. We help ambitious companies hire them.</p>
          <div className="ce-landing-ctas" aria-label="Explore enter">
            <button className="ce-landing-cta ce-landing-cta--companies" onClick={() => navigateToHiringSection('hire')}>For Companies</button>
            <button className="ce-landing-cta ce-landing-cta--candidates" onClick={openCandidate}>For Candidates</button>
          </div>
        </div>
      </div>
    </section>
    </div>

    <CompanyLogoMarquee />
  </LandingBackground>
    <div className="opening-landscape-wrap">
      <div className="hiring-scroll-light" aria-hidden="true" />
      <WhatAreYouBuilding />
    </div>
    <BrandStatement />
    <GrowthStages />
    <DeferredArtwork className="evidence-to-hires">
      <TalentPrinciples />
      <AmbitionHires />
    </DeferredArtwork>
    <WhenTeamsChange />
    <TestimonialsCarousel />
    <ForTalent onLogin={() => { sessionStorage.removeItem('enter-opportunity-intent'); window.scrollTo(0, 0); choose('candidate', 'login') }} onJoin={() => { sessionStorage.removeItem('enter-opportunity-intent'); window.scrollTo(0, 0); choose('candidate', 'signup') }} />
    <ClosingFooter onCandidate={openCandidate} onJoinNetwork={() => { sessionStorage.removeItem('enter-opportunity-intent'); window.scrollTo(0, 0); choose('candidate', 'signup') }} />
  </main>
}
