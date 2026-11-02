import observeLandingReveal from './observeLandingReveal'
import { useEffect, useRef } from 'react'
import './talent-principles.css'

const principles = [
  {
    conventional: <>They have the matching <b>KEYWORDS.</b></>,
    enter: <>We look for <b>ENGINEERING EVIDENCE.</b></>,
    evidence: 'WHAT THEY BUILT · TECH STACK · SYSTEM DESIGN · PRODUCTION USAGE · USERS / REQUESTS / DATA VOLUME',
  },
  {
    conventional: <>Their résumé shows <b>EXPOSURE</b> to the problem.</>,
    enter: <>We look for <b>DEPTH.</b></>,
    evidence: 'WHAT FAILED · WHY IT FAILED · FAILURE MODES · DEBUGGING · ROOT CAUSE · TRADE-OFFS',
  },
  {
    conventional: <>They have the right number of <b>YEARS.</b></>,
    enter: <>We look at <b>COMPLEXITY.</b></>,
    evidence: 'BOTTLENECKS · OPTIMIZATION · LATENCY · THROUGHPUT · CONCURRENCY · CONSTRAINTS',
  },
  {
    conventional: <>They have the relevant <b>DESIGNATION.</b></>,
    enter: <>We look at <b>SCOPE.</b></>,
    evidence: 'WHAT THEY OWNED · DECISIONS THEY MADE · SYSTEMS OWNED · TEAM SIZE · BUSINESS IMPACT',
  },
  {
    conventional: <>They say they <b>BUILT IT.</b></>,
    enter: <>We look for <b>PROOF.</b></>,
    evidence: 'BEFORE → AFTER · METRICS MOVED · WHAT SHIPPED · PRODUCTION IMPACT · CUSTOMER OUTCOME',
  },
] as const

const evidenceCards = [
  {
    label: 'BOTTLENECK FOUND',
    description: 'Checkout service hit 900ms P99 at peak traffic. Candidate isolated database contention.',
    tags: ['LATENCY', 'BOTTLENECK', 'ROOT CAUSE'],
    stage: 'SHIP',
  },
  {
    label: 'PRODUCTION FAILURE',
    description: 'Deployment caused elevated error rates. Candidate owned rollback and identified the failure mode.',
    tags: ['FAILURE MODE', 'DEBUGGING', 'OWNERSHIP'],
    stage: 'BREAK',
  },
  {
    label: 'OPTIMIZATION PROVEN',
    description: 'Redesigned caching strategy and reduced P99 latency from 900ms to 280ms.',
    tags: ['BEFORE → AFTER', 'PERFORMANCE', 'IMPACT'],
    stage: 'OPTIMIZE',
  },
] as const


export default function TalentPrinciples() {
  const sectionRef = useRef<HTMLElement>(null)

  useEffect(() => {
    const section = sectionRef.current
    if (section) return observeLandingReveal(section, 0.12)
  }, [])

  return <section ref={sectionRef} id="talent-principles" className="talent-principles" aria-labelledby="talent-principles-title">
    <div className="talent-principles__inner">
      <p className="talent-principles__eyebrow">HOW ENTER THINKS ABOUT TALENT</p>
      <div className="talent-principles__top">
        <header className="talent-principles__header">
          <h2 id="talent-principles-title">Getting it<br />wrong isn’t<br />an option.</h2>
        </header>

        <ul className="talent-principles__list">
          {principles.map((principle, index) => <li className="talent-principle" key={index}>
            <div className="talent-principle__comparison">
              <span className="talent-principle__conventional">{principle.conventional}</span>
              <span className="talent-principle__enter">{principle.enter}</span>
            </div>
            <p>{principle.evidence}</p>
          </li>)}
        </ul>
      </div>

      <div className="talent-evidence">
        <h3>WHAT EVIDENCE LOOKS LIKE</h3>

        <div className="talent-evidence__cards">
          {evidenceCards.map(card => <article className="talent-evidence-card" key={card.label}>
            <div className="talent-evidence-card__label"><i aria-hidden="true" />{card.label}</div>
            <p>{card.description}</p>
            <ul aria-label={`${card.label} evidence categories`}>
              {card.tags.map(tag => <li key={tag}>{tag}</li>)}
            </ul>
            <span className="talent-evidence-card__stage">CONNECTED STAGE: {card.stage}</span>
          </article>)}
        </div>
        <div className="talent-timeline" aria-label="Engineering evidence timeline">
          <div className="talent-timeline__reference-segments" aria-hidden="true">
            {Array.from({ length: 12 }, (_, index) => <span key={index} className={[1, 5, 9].includes(index) ? 'is-evidence' : ''} />)}
          </div>
          <ol className="talent-timeline__reference-labels">
            {['BUILD', 'SHIP', 'SCALE', 'BREAK', 'OPTIMIZE', 'IMPACT'].map(stage => <li key={stage}>{stage}</li>)}
          </ol>
        </div>
      </div>

      <footer className="talent-principles__closing">
        <p>We look beyond what someone has done <em>to understand how well they've done it.</em></p>
        <div>THAT DIFFERENCE IS WHERE <strong>GREAT HIRING BEGINS.</strong></div>
      </footer>
    </div>
  </section>
}
