import observeLandingReveal from './observeLandingReveal'
import { useEffect, useRef, useState } from 'react'
import type { FormEvent } from 'react'
import { createPortal } from 'react-dom'
import { ArrowRight } from 'lucide-react'
import { api } from '../api'
import './when-teams-change.css'

export default function WhenTeamsChange() {
  const sectionRef = useRef<HTMLElement>(null)
  const landscapeRef = useRef<HTMLDivElement>(null)
  const supportTriggerRef = useRef<HTMLButtonElement>(null)
  const supportDialogRef = useRef<HTMLDivElement>(null)
  const supportCloseRef = useRef<HTMLButtonElement>(null)
  const [supportOpen, setSupportOpen] = useState(false)
  const [reachMethod, setReachMethod] = useState<'list' | 'talk'>('list')
  const [submitState, setSubmitState] = useState<'idle' | 'sending' | 'sent'>('idle')
  const [submitError, setSubmitError] = useState('')

  const submitSupportRequest = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    if (submitState === 'sending') return
    setSubmitError('')
    setSubmitState('sending')
    const fields = new FormData(event.currentTarget)
    const body = new FormData()
    for (const [source, target] of [
      ['company', 'company'], ['name', 'full_name'], ['email', 'work_email'],
      ['role', 'role'], ['peopleImpacted', 'people_impacted'],
      ['lastWorkingDay', 'last_working_day'], ['reachMethod', 'reach_method'],
    ]) body.set(target, String(fields.get(source) ?? ''))
    body.set('consent', fields.has('consent') ? 'true' : 'false')
    if (reachMethod === 'list') {
      const file = fields.get('employeeList')
      if (file instanceof File && file.size) body.set('employee_list', file)
    } else {
      body.set('situation', String(fields.get('situation') ?? ''))
    }
    try {
      await api.submitEmployeeTransitionEnquiry(body)
      setSubmitState('sent')
    } catch (error) {
      setSubmitError(error instanceof Error ? error.message : 'We could not send your request. Please try again.')
      setSubmitState('idle')
    }
  }

  useEffect(() => {
    const section = sectionRef.current
    const landscape = landscapeRef.current
    if (!section || !landscape) return
    const stopSection = observeLandingReveal(section, .14)
    const stopLandscape = observeLandingReveal(landscape, .22, section, 'is-landscape-visible')
    return () => { stopSection(); stopLandscape() }
  }, [])

  useEffect(() => {
    if (!supportOpen) return
    const returnFocus = supportTriggerRef.current
    supportCloseRef.current?.focus()

    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        event.preventDefault()
        setSupportOpen(false)
        return
      }
      if (event.key !== 'Tab') return
      const dialog = supportDialogRef.current
      if (!dialog) return
      const focusable = Array.from(dialog.querySelectorAll<HTMLElement>(
        'button:not(:disabled), input:not(:disabled), select:not(:disabled), textarea:not(:disabled), a[href], [tabindex]:not([tabindex="-1"])',
      ))
      const first = focusable[0]
      const last = focusable[focusable.length - 1]
      if (!first || !last) return
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault()
        last.focus()
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault()
        first.focus()
      }
    }

    document.addEventListener('keydown', handleKeyDown)
    return () => {
      document.removeEventListener('keydown', handleKeyDown)
      returnFocus?.focus({ preventScroll: true })
    }
  }, [supportOpen])

  return <section ref={sectionRef} className="when-teams-change" aria-labelledby="when-teams-change-title">
    <div className="when-teams-change__content">
      <header className="when-teams-change__header">
        <p>WHEN TEAMS CHANGE</p>
        <h2 id="when-teams-change-title">
          <span className="when-teams-change__opening">The impact we create extends across entire organizations.</span>
          <span className="when-teams-change__human"><em>but.....</em> it always starts with the people who shape them.</span>
        </h2>
      </header>

      <p className="when-teams-change__supporting">When roles end, responsibility doesn’t have to.</p>

      <div className="when-teams-change__copy">
        <div className="when-teams-change__copy-group">
          <p>A layoff may be a business decision. For the person receiving it, it can change everything overnight.</p>
        </div>
        <p>ENTER helps you make that transition a little less difficult.</p>
        <p>Give impacted employees a direct path into our hiring network, where their experience is understood, their work is represented with context, and they can be considered for opportunities where they genuinely belong.</p>
      </div>

      <div className="when-teams-change__action">
        <button
          ref={supportTriggerRef}
          type="button"
          aria-haspopup="dialog"
          aria-expanded={supportOpen}
          aria-controls="employee-transition-dialog"
          onClick={() => { setSubmitState('idle'); setSubmitError(''); setSupportOpen(true) }}
        >
          Support Your People <ArrowRight size={17} aria-hidden="true" />
        </button>
      </div>
    </div>

    <div ref={landscapeRef} className="when-teams-change__landscape">
      <p><em>Because every exit deserves the possibility of an entrance.</em></p>
    </div>
    {supportOpen && createPortal(
      <div
        className="when-teams-change__dialog-backdrop"
        onMouseDown={event => { if (event.target === event.currentTarget) setSupportOpen(false) }}
      >
        <div
          ref={supportDialogRef}
          id="employee-transition-dialog"
          className="when-teams-change__dialog"
          role="dialog"
          aria-modal="true"
          aria-labelledby="employee-transition-title"
          aria-describedby="employee-transition-description"
          tabIndex={-1}
        >
          <div className="when-teams-change__dialog-heading">
            <div>
              <h2 id="employee-transition-title">Help your people find what’s next.</h2>
            </div>
            <button ref={supportCloseRef} type="button" aria-label="Close support form" onClick={() => setSupportOpen(false)}>×</button>
          </div>
          <p id="employee-transition-description" className="when-teams-change__visually-hidden">Share a few details about the people you want to support.</p>
          {submitState === 'sent' ? <p className="when-teams-change__success" role="status">Thank you. Your request has been received. Our team will follow up at your work email.</p> : <form className="when-teams-change__form" onSubmit={submitSupportRequest}>
            <div className="when-teams-change__form-grid">
              <input aria-label="Company" name="company" type="text" placeholder="Your company name" required />
              <input aria-label="Your name" name="name" type="text" placeholder="Full name" autoComplete="name" required />
              <input aria-label="Work email" name="email" type="email" placeholder="Work email" autoComplete="email" required />
              <select aria-label="Your role" name="role" defaultValue="" required><option value="" disabled>Your role</option><option>HR</option><option>People</option><option>Founder</option><option>Other</option></select>
              <select aria-label="People impacted" name="peopleImpacted" defaultValue="" required><option value="" disabled>People impacted</option><option>1–10</option><option>11–40</option><option>41–100</option><option>More than 100</option></select>
              <label className="when-teams-change__date-field"><span>Last working day</span><input aria-label="Last working day" name="lastWorkingDay" type="date" required /></label>
            </div>
            <fieldset className="when-teams-change__reach" aria-label="How should we reach your people?">
              <label className={reachMethod === 'list' ? 'is-selected' : ''}>
                <input type="radio" name="reachMethod" value="list" checked={reachMethod === 'list'} onChange={() => setReachMethod('list')} />
                <span><strong>Upload a list</strong><small>An Excel or CSV sheet with name, role and email. We would invite each person only with their consent.</small></span>
              </label>
              <label className={reachMethod === 'talk' ? 'is-selected' : ''}>
                <input type="radio" name="reachMethod" value="talk" checked={reachMethod === 'talk'} onChange={() => setReachMethod('talk')} />
                <span><strong>Talk to us first</strong><small>Tell us about the situation and we can discuss the next step together.</small></span>
              </label>
            </fieldset>
            {reachMethod === 'list' && <label className="when-teams-change__file"><span className="when-teams-change__visually-hidden">Choose an Excel or CSV list</span><input type="file" name="employeeList" accept=".csv,.xlsx,text/csv,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" aria-label="Choose an Excel or CSV list" required /></label>}
            {reachMethod === 'talk' && <textarea className="when-teams-change__situation" name="situation" aria-label="Tell us about the situation" placeholder="Tell us a little about the situation" rows={2} required />}
            <label className="when-teams-change__consent"><input type="checkbox" name="consent" required /><span>I confirm affected employees know about this, and nothing is shared without their consent.</span></label>
            <div className="when-teams-change__form-footer">
              <button type="submit" disabled={submitState === 'sending'}>{submitState === 'sending' ? 'Sending…' : 'Submit'} {submitState !== 'sending' && <ArrowRight size={16} aria-hidden="true" />}</button>
            </div>
            {submitError && <p className="when-teams-change__dialog-note" role="alert">{submitError}</p>}
          </form>}
        </div>
      </div>,
      document.body,
    )}
  </section>
}
