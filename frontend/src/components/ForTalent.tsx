import observeLandingReveal from './observeLandingReveal'
import { useEffect, useRef } from 'react'
import { ArrowRight } from 'lucide-react'
import './for-talent.css'

const talentCategories = ['AI & ML', 'Engineering', 'Product', 'Leadership'] as const

export default function ForTalent({ onJoin }: { onJoin: () => void }) {
  const sectionRef = useRef<HTMLElement>(null)

  useEffect(() => {
    const section = sectionRef.current
    if (section) return observeLandingReveal(section, 0.2)
  }, [])

  return <section ref={sectionRef} className="for-talent" aria-labelledby="for-talent-title">
    <div className="for-talent__inner">
      <div className="for-talent__content">
        <p className="for-talent__eyebrow">FOR TALENT</p>
        <h2 id="for-talent-title" aria-label="Let's find work that feels great.">Let's find work that<br />feels great.</h2>
        <p className="for-talent__description">Find opportunities with ambitious companies building what's next.</p>
        <p className="for-talent__category-line">AI &amp; ML · ENGINEERING · PRODUCT · LEADERSHIP</p>
        <button type="button" onClick={onJoin}>
          Join enter’s talent network <ArrowRight size={16} aria-hidden="true" />
        </button>
      </div>

      <ul className="for-talent__categories" aria-label="Talent categories">
        {talentCategories.map(category => <li key={category}>{category}</li>)}
      </ul>
    </div>
  </section>
}
