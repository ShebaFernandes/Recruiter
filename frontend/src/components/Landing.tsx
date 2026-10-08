import { useEffect, useRef } from 'react'
import { ArrowRight, MoveUpRight } from 'lucide-react'
import { Button } from './ui'
import './landing.css'

export default function Landing({ choose }: {
  choose: (role: 'recruiter' | 'candidate', mode?: 'signup' | 'login') => void
}) {
  const root = useRef<HTMLElement>(null)

  useEffect(() => {
    const targets = root.current?.querySelectorAll('.ce-reveal')
    if (!targets || typeof window.IntersectionObserver !== 'function'
      || window.matchMedia('(prefers-reduced-motion: reduce)').matches) return
    let observer: IntersectionObserver | undefined
    try {
      observer = new IntersectionObserver(entries => {
        entries.forEach(entry => {
          if (entry.isIntersecting) {
            entry.target.classList.add('is-revealed')
            observer?.unobserve(entry.target)
          }
        })
      }, { threshold: 0.12 })
      targets.forEach(target => observer?.observe(target))
    } catch {
      // Animation is optional: leave all content visible if observation fails.
      observer?.disconnect()
      return
    }
    return () => observer?.disconnect()
  }, [])

  return <main className="career-edition" ref={root}>
    <a className="ce-skip" href="#enter-home">Skip to content</a>
    <header className="ce-masthead">
      <a className="ce-logo" href="#enter-home" aria-label="Enter home"><img src="/enter-logo.jpeg" alt="enter" /></a>
      <span className="ce-masthead-note">People. Work. Possibility.</span>
      <nav aria-label="Main navigation">
        <a href="#recruiter-entry">For recruiters <MoveUpRight size={13} aria-hidden="true" /></a>
        <a href="#candidate-entry">For candidates <MoveUpRight size={13} aria-hidden="true" /></a>
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
      <div className="ce-index"><span>THE ENTER PERSPECTIVE</span><span>01 / PEOPLE, IN CONTEXT</span></div>
      <div className="ce-intro-grid">
        <h1 id="ce-title">A career is more<br />than a <em>job title.</em></h1>
        <div className="ce-intro-aside">
          <p>Enter helps recruiters discover the people behind the résumé and candidates share the work that matters.</p>
        </div>
      </div>
    </section>

    <section className="ce-entry-section" aria-labelledby="ce-entry-title">
      <div className="ce-page-width">
        <div className="ce-entry-heading"><span className="ce-kicker">02 / THE NEXT CHAPTER</span><h2 id="ce-entry-title">Two perspectives.<br /><em>One meaningful connection.</em></h2></div>
        <article className="ce-entry ce-reveal" id="recruiter-entry" aria-labelledby="ce-recruiter-title">
          <span className="ce-entry-number">01</span>
          <div className="ce-entry-copy"><span className="ce-kicker">FOR RECRUITERS</span><h3 id="ce-recruiter-title">Find the person<br />behind the keywords.</h3></div>
          <div className="ce-entry-action"><p>Describe the work. Explore the evidence. Build a shortlist with a better understanding of the people on it.</p><Button variant="secondary" onClick={() => choose('recruiter')} data-testid="for-recruiters">Enter recruiter workspace <ArrowRight size={17} aria-hidden="true" /></Button></div>
        </article>
        <article className="ce-entry ce-reveal" id="candidate-entry" aria-labelledby="ce-candidate-title">
          <span className="ce-entry-number">02</span>
          <div className="ce-entry-copy"><span className="ce-kicker">FOR CANDIDATES</span><h3 id="ce-candidate-title">Let your work<br />tell a fuller story.</h3></div>
          <div className="ce-entry-action"><p>Start with your résumé. Add what matters to you. Choose how recruiters discover your profile—and what comes next.</p><Button variant="secondary" onClick={() => choose('candidate')} data-testid="for-candidates">Build your candidate profile <ArrowRight size={17} aria-hidden="true" /></Button></div>
        </article>
      </div>
    </section>
    <footer className="ce-footer ce-page-width"><a className="ce-logo" href="#enter-home" aria-label="Enter home"><img src="/enter-logo.jpeg" alt="enter" /></a><p>Good work begins with understanding people.</p><a href="#enter-home">Back to top ↑</a></footer>
  </main>
}
