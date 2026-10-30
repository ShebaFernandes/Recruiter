import useLandingMotion from './useLandingMotion'
import { ArrowRight } from 'lucide-react'
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
  // Candidate screens are selected in app state, so lower-page CTAs must reset the scroll.
  const openCandidate = () => {
    choose('candidate')
    window.scrollTo({ top: 0, behavior: 'instant' })
  }

  return <main className="career-edition simple-landing"><LandingBackground>
    <a className="ce-skip" href="#enter-home">Skip to content</a>
    <div className="ce-mountain-hero">
    <header className="ce-masthead">
      <div className="ce-brand-lockup">
      <a className="ce-logo" href="#enter-home" aria-label="enter home"><span className="ce-uppercase-logo">ENTER</span></a>
      <span className="ce-masthead-note">Humanity. Integrity and Possibility.</span>
      </div>
      <nav aria-label="Main navigation">
        {import.meta.env.VITE_CANDIDATE_ONLY !== 'true' && <button className="ce-audience-link" data-testid="for-recruiters" onClick={() => choose('recruiter', 'login')}>For Recruiters</button>}
        <button className="ce-audience-link" data-testid="for-companies" onClick={() => navigateToHiringSection('hire')}>For Companies</button>
        <button className="ce-audience-link" data-testid="for-candidates" onClick={() => choose('candidate')}>For Candidates</button>
        <details className="ce-login" onBlur={event => {
          if (!event.currentTarget.contains(event.relatedTarget)) event.currentTarget.open = false
        }} onKeyDown={event => {
          if (event.key === 'Escape') {
            event.currentTarget.open = false
            event.currentTarget.querySelector('summary')?.focus()
          }
        }}>
          <summary>Log in</summary>
          <div className="ce-login-options">
            {import.meta.env.VITE_CANDIDATE_ONLY !== 'true' && <button onClick={() => choose('recruiter', 'login')}>Recruiter log in <ArrowRight size={14} aria-hidden="true" /></button>}
            <button onClick={() => choose('candidate', 'login')}>Candidate log in <ArrowRight size={14} aria-hidden="true" /></button>
          </div>
        </details>
      </nav>
    </header>

    <section className="ce-intro ce-page-width" id="enter-home" tabIndex={-1} aria-labelledby="ce-title">
      <div className="ce-intro-grid">
        <h1 id="ce-title" aria-label="The best teams are built by enter.">The best teams are<br />built by <span className="ce-headline-brand" aria-hidden="true"><span className="ce-uppercase-headline">ENTER</span>.</span></h1>
        <div className="ce-intro-aside">
          <p className="ce-supporting-headline">What You Build Tomorrow Depends on Who You Hire Today</p>
          <p>Every breakthrough product, high-performing team, and successful company is built by exceptional people. We help ambitious companies hire them.</p>
          <div className="ce-landing-ctas" aria-label="Explore enter">
            <button className="ce-landing-cta ce-landing-cta--companies" onClick={() => navigateToHiringSection('hire')}>For Companies</button>
            <button className="ce-landing-cta ce-landing-cta--candidates" onClick={() => choose('candidate')}>For Candidates</button>
          </div>
        </div>
      </div>
    </section>
    </div>

    <CompanyLogoMarquee />
  </LandingBackground>
    <WhatAreYouBuilding />
    <BrandStatement />
    <GrowthStages />
    <div className="evidence-to-hires">
      <TalentPrinciples />
      <AmbitionHires />
    </div>
    <WhenTeamsChange />
    <TestimonialsCarousel />
    <ForTalent onJoin={openCandidate} />
    <ClosingFooter onCandidate={openCandidate} />
  </main>
}
