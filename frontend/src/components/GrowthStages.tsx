import observeLandingReveal from './observeLandingReveal'
import { useEffect, useLayoutEffect, useRef, useState } from 'react'
import GrowthEnquiry from './GrowthEnquiry'
import './growth-stages.css'

const stages = [
  {
    marker: '0 → 1',
    category: 'FOUNDING TEAMS',
    heading: 'Your first few people shape everything that follows.',
    description: 'We find the early builders who can turn an idea into a product — and build the technical foundations for what comes next.',
    specializations: 'FOUNDING ENGINEERS · FOUNDING AI/ML · EARLY TECHNICAL LEADERS',
    cta: 'Build Your Founding Team',
    image: '/media/growth-stages/founding-teams-hills.png',
    imageAlt: 'Rolling green and gold hills in warm evening light',
    tone: 'founding',
  },
  {
    marker: 'SCALE →',
    category: 'LEADERSHIP',
    heading: 'The right leader changes what an entire team can become.',
    description: 'We find leaders who can raise the bar, build exceptional teams and lead the company through its next stage of scale.',
    specializations: 'ENGINEERING LEADERS · PRODUCT LEADERS · FUNCTIONAL LEADERS',
    cta: 'Find Leadership',
    image: '/media/growth-stages/leadership-mountain-valley.png',
    imageAlt: 'A misty blue-gray mountain valley beneath alpine peaks',
    tone: 'leadership',
  },
] as const

export default function GrowthStages() {
  const sectionRef = useRef<HTMLElement>(null)
  const movingCard = useRef<{ tone: 'founding' | 'leadership'; rect: DOMRect } | null>(null)
  const [active, setActive] = useState<'founding' | 'leadership' | null>(null)

  useEffect(() => {
    const section = sectionRef.current
    if (section) return observeLandingReveal(section, 0.2)
  }, [])

  useLayoutEffect(() => {
    const previous = movingCard.current
    movingCard.current = null
    if (!previous || window.matchMedia?.('(prefers-reduced-motion: reduce)').matches) return

    const card = sectionRef.current?.querySelector<HTMLElement>(`.growth-stage-card--${previous.tone}`)
    if (!card?.animate) return
    const next = card.getBoundingClientRect()
    const offsetX = previous.rect.left - next.left
    const offsetY = previous.rect.top - next.top
    const scaleX = previous.rect.width / next.width
    const scaleY = previous.rect.height / next.height

    card.animate([
      { transform: `translate(${offsetX}px, ${offsetY}px) scale(${scaleX}, ${scaleY})` },
      { transform: 'translate(0, 0) scale(1, 1)' },
    ], { duration: 620, easing: 'cubic-bezier(.22, 1, .36, 1)' })
  }, [active])

  const openEnquiry = (tone: 'founding' | 'leadership', card: HTMLElement) => {
    movingCard.current = { tone, rect: card.getBoundingClientRect() }
    setActive(tone)
  }

  const closeEnquiry = () => {
    if (active) {
      const card = sectionRef.current?.querySelector<HTMLElement>(`.growth-stage-card--${active}`)
      if (card) movingCard.current = { tone: active, rect: card.getBoundingClientRect() }
    }
    setActive(null)
  }

  return <section ref={sectionRef} className={`growth-stages${active ? ' growth-stages--enquiry' : ''}`} aria-labelledby="growth-stages-title">
    <div className="growth-stages__inner">
      <header className="growth-stages__header">
        <p className="growth-stages__eyebrow">TAILORED FOR EVERY STAGE OF GROWTH</p>
        <h2 id="growth-stages-title">From the people who start it to the people who scale it.</h2>
        <p className="growth-stages__intro">
          Whether you're building your founding team, scaling fast, or strengthening your leadership,{' '}
          enter helps you find the people you need at every stage of growth.
        </p>
      </header>

      <div className="growth-stages__progress" aria-hidden="true">
        <span>0 → 1</span>
        <i />
        <span>SCALE →</span>
      </div>

      <div className={`growth-stages__grid${active ? ` growth-stages__grid--enquiry growth-stages__grid--${active}` : ''}`}>
        {active && <GrowthEnquiry key={active} kind={active} onClose={closeEnquiry} />}
        {stages.filter(stage => !active || stage.tone === active).map(stage => <article className={`growth-stage-card growth-stage-card--${stage.tone}`} key={stage.category}>
          <div className="growth-stage-card__body">
            <p className="growth-stage-card__marker">{stage.marker}</p>
            <p className="growth-stage-card__category">{stage.category}</p>
            <h3>{stage.heading}</h3>
            <p className="growth-stage-card__description">{stage.description}</p>
            <p className="growth-stage-card__specializations">{stage.specializations}</p>
            <button type="button" className="growth-stage-card__cta" onClick={event => openEnquiry(stage.tone, event.currentTarget.closest<HTMLElement>('.growth-stage-card')!)}>
              {stage.cta}
            </button>
          </div>
          <img className="growth-stage-card__image" src={stage.image} alt={stage.imageAlt} />
        </article>)}
      </div>


    </div>
  </section>
}
