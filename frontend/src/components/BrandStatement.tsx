import observeLandingReveal from './observeLandingReveal'
import { Fragment, useEffect, useRef, type CSSProperties } from 'react'
import './brand-statement.css'

const beforeHighlight = ['The', 'right', 'person', 'changes']
const afterHighlight = ['the', 'pace', 'and', 'the', 'possibility', 'of', 'what', 'comes', 'next.']
const word = (text: string, index: number) => <span className="brand-statement__word" style={{ '--word-index': index } as CSSProperties}>{text}</span>

export default function BrandStatement() {
  const sectionRef = useRef<HTMLElement>(null)

  useEffect(() => {
    const section = sectionRef.current
    if (section) return observeLandingReveal(section, 0.3)
  }, [])

  return <section ref={sectionRef} className="brand-statement" aria-labelledby="brand-statement-title">
    <div className="brand-statement__inner">
      <h2 id="brand-statement-title" className="brand-statement__copy">
        {beforeHighlight.map((text, index) => <Fragment key={index}>{word(text, index)}{' '}</Fragment>)}
        <em>{word('the', 4)}{' '}{word('product,', 5)}</em>{' '}
        {afterHighlight.map((text, index) => <Fragment key={index}>{index > 0 && ' '}{word(text, index + 6)}</Fragment>)}
      </h2>
    </div>
  </section>
}
