import { lazy, Suspense } from 'react'
import { ArrowRight } from 'lucide-react'
import MountainHero from './MountainHero'
import { isCompanyPreviewAllowed } from './companyPreviewGate'
import './landing.css'

// Vite removes this branch, its module, and imported company assets in production.
// Public-display permission has NOT been granted.
const CompanyLogoPreview = import.meta.env.DEV
  ? lazy(() => import('./company-preview/CompanyLogoPreview')) : null

export default function Landing({ choose }: {
  choose: (role: 'recruiter' | 'candidate', mode?: 'signup' | 'login') => void
}) {
  return <main className="career-edition">
    <a className="ce-skip" href="#enter-home">Skip to content</a>
    <div className="ce-mountain-hero">
    <MountainHero />
    <header className="ce-masthead">
      <a className="ce-logo" href="#enter-home" aria-label="Enter home"><img src="/enter-wordmark.svg" alt="enter" width={1400} height={600} /></a>
      <span className="ce-masthead-note">People. Work. Possibility.</span>
      <nav aria-label="Main navigation">
        {/* Guest search needs a separately approved secure backend. Keep this
            entry protected in the meantime, without the old scroll detour. */}
        <button className="ce-audience-link" data-testid="for-recruiters" onClick={() => choose('recruiter')}>For recruiters</button>
        <button className="ce-audience-link" data-testid="for-candidates" onClick={() => choose('candidate')}>For candidates</button>
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
            <button onClick={() => choose('recruiter', 'login')}>Recruiter log in <ArrowRight size={14} aria-hidden="true" /></button>
            <button onClick={() => choose('candidate', 'login')}>Candidate log in <ArrowRight size={14} aria-hidden="true" /></button>
          </div>
        </details>
      </nav>
    </header>

    <section className="ce-intro ce-page-width" id="enter-home" tabIndex={-1} aria-labelledby="ce-title">
      <div className="ce-intro-grid">
        <h1 id="ce-title" aria-label="The best teams are built by ENTER.">The best teams are<br />built by <span className="ce-headline-brand" aria-hidden="true"><svg className="ce-headline-wordmark" viewBox="145 145 1110 310" focusable="false"><image href="/enter-wordmark.svg" width="1400" height="600" /></svg>.</span></h1>
        <div className="ce-intro-aside">
          <p className="ce-supporting-headline">What You Build Tomorrow Depends on Who You Hire Today</p>
          <p>Every breakthrough product, high-performing team, and successful company is built by exceptional people. We help ambitious companies hire them.</p>
        </div>
      </div>
    </section>
    </div>

    {CompanyLogoPreview && isCompanyPreviewAllowed(import.meta.env.DEV, window.location.hostname, window.location.search)
      && <Suspense fallback={null}><CompanyLogoPreview /></Suspense>}

  </main>
}
