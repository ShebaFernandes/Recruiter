import MountainHero from './MountainHero'
import CompanyLogoMarquee from './company-preview/CompanyLogoPreview'
import './landing.css'

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
        <button className="ce-audience-link" data-testid="for-recruiters" onClick={() => choose('recruiter')}>For recruiters</button>
        <button className="ce-audience-link" data-testid="for-candidates" onClick={() => choose('candidate')}>For candidates</button>
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

    <CompanyLogoMarquee />

  </main>
}
