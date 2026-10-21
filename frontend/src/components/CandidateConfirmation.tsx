import { useEffect, useRef } from 'react'
import { ArrowRight, CircleCheck, MessageCircle, Search } from 'lucide-react'
import { AnimatedTicket } from './ui/ticket-confirmation-card'
import './candidate-confirmation.css'

export default function CandidateConfirmation({ onViewProfile }: { onViewProfile: () => void }) {
  const heading = useRef<HTMLHeadingElement>(null)
  useEffect(() => {
    heading.current?.focus({ preventScroll: true })
    window.scrollTo({ top: 0, behavior: 'instant' })
  }, [])

  return <section className="cp-success cp-confirmation" aria-labelledby="confirmation-title">
    <AnimatedTicket>
    <p className="cp-confirmation-eyebrow">PROFILE SUBMITTED</p>
    <div className="cp-ticket-check"><CircleCheck aria-hidden="true" /></div>
    <h2 id="confirmation-title" ref={heading} tabIndex={-1}>You're in.</h2>
    <div className="cp-confirmation-content">
      <h3>We'll take it from here.</h3>
      <p className="cp-confirmation-message">Your profile has been submitted successfully. When a relevant opportunity comes along, ENTER can help connect you with the right people.</p>
      <section className="cp-confirmation-next" aria-labelledby="confirmation-next-title">
        <h4 id="confirmation-next-title">What happens next?</h4>
        <ul>
          <li><CircleCheck aria-hidden="true" /><div><h5>Your profile is saved</h5><p>Your experience and career preferences are securely recorded.</p></div></li>
          <li><Search aria-hidden="true" /><div><h5>Relevant recruiters can discover you</h5><p>When your profile matches their search and your availability settings permit discovery.</p></div></li>
          <li><MessageCircle aria-hidden="true" /><div><h5>We'll be in touch</h5><p>If there's a relevant opportunity, you'll be contacted according to your saved preferences.</p></div></li>
        </ul>
      </section>
      <button type="button" className="cp-confirmation-profile" onClick={onViewProfile}>View my profile <ArrowRight aria-hidden="true" /></button>
    </div>
    </AnimatedTicket>
  </section>
}
