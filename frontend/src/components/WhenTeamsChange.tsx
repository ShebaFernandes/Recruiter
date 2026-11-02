import observeLandingReveal from './observeLandingReveal'
import { useEffect, useRef, useState } from 'react'
import type { FormEvent } from 'react'
import { createPortal } from 'react-dom'
import { ArrowRight, ChevronDown, Paperclip } from 'lucide-react'
import { api } from '../api'
import './when-teams-change.css'

function TransitionSelect({ name, label, options }: { name: string; label: string; options: string[] }) {
  const [value, setValue] = useState('')
  const [open, setOpen] = useState(false)
  const root = useRef<HTMLDivElement>(null)
  const trigger = useRef<HTMLButtonElement>(null)
  useEffect(() => {
    if (!open) return
    const close = (event: MouseEvent) => {
      if (!root.current?.contains(event.target as Node)) setOpen(false)
    }
    document.addEventListener('mousedown', close)
    return () => document.removeEventListener('mousedown', close)
  }, [open])
  return <div ref={root} className="transition-select" onBlur={event => {
    if (!event.currentTarget.contains(event.relatedTarget)) setOpen(false)
  }} onKeyDown={event => {
    if (event.key === 'Escape' && open) { event.stopPropagation(); setOpen(false); trigger.current?.focus() }
    if (event.key === 'ArrowDown' || event.key === 'ArrowUp') {
      event.preventDefault()
      setOpen(true)
      requestAnimationFrame(() => {
        const items = Array.from(root.current?.querySelectorAll<HTMLButtonElement>('[role="option"]') ?? [])
        const index = items.indexOf(document.activeElement as HTMLButtonElement)
        items[(index + (event.key === 'ArrowDown' ? 1 : -1) + items.length) % items.length]?.focus()
      })
    }
  }}>
    <input type="text" className="when-teams-change__visually-hidden" tabIndex={-1} aria-label={label} name={name} value={value} required onChange={() => {}} onInvalid={() => trigger.current?.focus()} />
    <button ref={trigger} type="button" aria-label={label} aria-haspopup="listbox" aria-expanded={open} className={value ? 'has-value' : ''} onClick={() => setOpen(!open)}>{value || label}<ChevronDown className="transition-select__arrow" size={16} strokeWidth={1.5} aria-hidden="true" /></button>
    {open && <div role="listbox" aria-label={label} className="transition-select__menu">{options.map(option => <button type="button" role="option" aria-selected={value === option} key={option} onClick={() => { setValue(option); setOpen(false); trigger.current?.focus() }}>{option}</button>)}</div>}
  </div>
}

export default function WhenTeamsChange() {
  const fileRef = useRef<HTMLInputElement>(null)
  const [fileName, setFileName] = useState('')
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
      ['phone', 'phone'], ['reachMethod', 'reach_method'],
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
          <span className="when-teams-change__human"><em>but..</em> it always starts with the people who shape them.</span>
        </h2>
      </header>

      <p className="when-teams-change__supporting">When roles end, responsibility doesn’t have to.</p>

      <div className="when-teams-change__copy">
        <div className="when-teams-change__copy-group">
          <p>A layoff may be a business decision. For the person receiving it, it can change everything overnight.</p>
        </div>
        <p>enter helps you make that transition a little less difficult.</p>
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
          <p id="employee-transition-description" className="when-teams-change__dialog-description">We help impacted employees become visible to companies that are still building and find the opportunity that comes next.</p>
          {submitState === 'sent' ? <p className="when-teams-change__success" role="status">Thank you. Your request has been received. Our team will follow up at your work email.</p> : <form className="when-teams-change__form" onSubmit={submitSupportRequest}>
            <div className="when-teams-change__form-grid">
              <label className="when-teams-change__field"><input aria-label="Company" name="company" type="text" placeholder="Your company name" required /></label>
              <label className="when-teams-change__field"><input aria-label="Your name" name="name" type="text" placeholder="Your name" autoComplete="name" required /></label>
              <label className="when-teams-change__field"><input aria-label="Work email" name="email" type="email" placeholder="Work email" autoComplete="email" required /></label>
              <label className="when-teams-change__field"><TransitionSelect name="role" label="Your role" options={["HR", "People", "Founder", "Other"]} /></label>
              <label className="when-teams-change__field"><TransitionSelect name="peopleImpacted" label="People impacted" options={["1–10", "11–40", "41–100", "More than 100"]} /></label>
              <label className="when-teams-change__field"><input aria-label="Phone number" name="phone" type="tel" autoComplete="tel" placeholder="Phone number" maxLength={40} required /></label>
            </div>
            <fieldset className="when-teams-change__reach" aria-label="How should we reach your people?"><legend>How should we reach your people?</legend>
              <div className={`transition-contact-option${reachMethod === 'list' ? ' is-selected' : ''}`}>
                <label className="transition-contact-option__choice"><input type="radio" name="reachMethod" value="list" checked={reachMethod === 'list'} onChange={() => setReachMethod('list')} /><span><strong>Upload a list</strong><small>Share an Excel or CSV with name, role and email. Each person chooses whether to participate.</small></span></label>
                {reachMethod === 'list' && <label className="transition-contact-option__upload"><Paperclip size={16} aria-hidden="true" /><span><strong>{fileName || 'Choose a file to upload'}</strong><small>Excel (.xlsx) or CSV · Up to 2 MB</small></span><input ref={fileRef} type="file" required name="employeeList" accept=".csv,.xlsx,text/csv,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" aria-label="Choose an Excel or CSV list" onChange={event => setFileName(event.target.files?.[0]?.name ?? '')} /></label>}
              </div>
              <div className={`transition-contact-option${reachMethod === 'talk' ? ' is-selected' : ''}`}>
                <label className="transition-contact-option__choice"><input type="radio" name="reachMethod" value="talk" checked={reachMethod === 'talk'} onChange={() => setReachMethod('talk')} /><span><strong>Talk to us first</strong><small>Tell us what you need. We’ll respond within one working day.</small></span></label>
                {reachMethod === 'talk' && <textarea className="when-teams-change__situation" name="situation" aria-label="Tell us about the situation" placeholder="How can we help your team?" maxLength={2000} rows={2} />}
              </div>
            </fieldset>

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
