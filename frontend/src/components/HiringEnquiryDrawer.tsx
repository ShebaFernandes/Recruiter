import { useEffect, useId, useRef, useState, type FormEvent } from 'react'
import { createPortal } from 'react-dom'
import { ChevronDown, Paperclip, X } from 'lucide-react'
import { api } from '../api'
import './hiring-enquiry-drawer.css'

export type HiringEnquiry = {
  kind: 'hire' | 'team' | 'drive'
  role?: string
  teamFocus?: string
  location?: string
  headcount: number
  deadline?: string
  workEmail?: string
  showStats?: boolean
}

const departments = ['Engineering', 'Product', 'Marketing', 'Business', 'Other']
const personalDomains = new Set(['gmail.com', 'yahoo.com', 'outlook.com', 'hotmail.com', 'live.com', 'icloud.com', 'aol.com', 'proton.me', 'protonmail.com', 'rediffmail.com'])
const config = {
  hire: { title: "Let's find your next great hire.", description: "Tell us who you're looking for. We'll help you find the right people.", action: 'Find Talent', department: 'Role departments' },
  team: { title: "Let's build your team.", description: "Tell us about the team you're creating and the people you need.", action: 'Build My Team', department: 'Team departments' },
  drive: { title: "Let's plan your hiring drive.", description: 'Tell us about your hiring targets and timeline.', action: 'Plan My Drive', department: 'Hiring departments' },
} as const

function validWorkEmail(value: string) {
  if (!/^[a-zA-Z0-9!#$%&'*+/=?^_`{|}~-]+(?:\.[a-zA-Z0-9!#$%&'*+/=?^_`{|}~-]+)*@(?:[a-zA-Z0-9](?:[a-zA-Z0-9-]*[a-zA-Z0-9])?\.)+[a-zA-Z]{2,}$/.test(value)) return false
  return !personalDomains.has(value.split('@')[1].toLowerCase())
}

export default function HiringEnquiryDrawer({ enquiry, minimumDate, opener, onClose }: {
  enquiry: HiringEnquiry; minimumDate: string; opener: HTMLButtonElement | null; onClose: () => void
}) {
  const panelRef = useRef<HTMLDivElement>(null)
  const closeRef = useRef<HTMLButtonElement>(null)
  const fileRef = useRef<HTMLInputElement>(null)
  const titleId = useId()
  const [closing, setClosing] = useState(false)
  const [name, setName] = useState('')
  const [company, setCompany] = useState('')
  const [email, setEmail] = useState(enquiry.workEmail ?? '')
  const [selfDescription, setSelfDescription] = useState('')
  const [otherDescription, setOtherDescription] = useState('')
  const [role, setRole] = useState(enquiry.role ?? '')
  const [teamFocus, setTeamFocus] = useState(enquiry.teamFocus ?? '')
  const [location, setLocation] = useState(enquiry.location ?? '')
  const [editingContext, setEditingContext] = useState(false)
  const [deadline, setDeadline] = useState(enquiry.deadline ?? '')
  const [headcount, setHeadcount] = useState(enquiry.headcount ? String(enquiry.headcount) : '')
  const [selected, setSelected] = useState<string[]>([])
  const [file, setFile] = useState<File | null>(null)
  const [notes, setNotes] = useState('')
  const [howSoon, setHowSoon] = useState('')
  const [driveMode, setDriveMode] = useState('In person')
  const [expectedCandidates, setExpectedCandidates] = useState('')
  const [teamStage, setTeamStage] = useState('A brand-new team')
  const [otherDepartment, setOtherDepartment] = useState('')
  const [otherTiming, setOtherTiming] = useState('')
  const [dragging, setDragging] = useState(false)
  const [errors, setErrors] = useState<Record<string, string>>({})
  const [submitState, setSubmitState] = useState<'idle' | 'sending' | 'sent'>('idle')
  const [submitError, setSubmitError] = useState('')
  const details = config[enquiry.kind]
  const close = () => setClosing(true)

  useEffect(() => {
    const main = opener?.closest('main')
    const oldInert = main?.inert
    const oldOverflow = document.body.style.overflow
    if (main) main.inert = true
    document.body.style.overflow = 'hidden'
    closeRef.current?.focus()
    return () => {
      if (main) main.inert = oldInert ?? false
      document.body.style.overflow = oldOverflow
      opener?.focus({ preventScroll: true })
    }
  }, [opener])

  useEffect(() => {
    if (!closing) return
    const reduced = window.matchMedia?.('(prefers-reduced-motion: reduce)').matches
    const timer = window.setTimeout(onClose, reduced ? 0 : 300)
    return () => window.clearTimeout(timer)
  }, [closing, onClose])

  useEffect(() => {
    const keydown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') { event.preventDefault(); close(); return }
      if (event.key !== 'Tab' || !panelRef.current) return
      const items = Array.from(panelRef.current.querySelectorAll<HTMLElement>('button:not(:disabled), input:not(:disabled):not([type="hidden"]), textarea:not(:disabled), [href]'))
      const first = items[0]; const last = items[items.length - 1]
      if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last?.focus() }
      else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first?.focus() }
    }
    document.addEventListener('keydown', keydown)
    return () => document.removeEventListener('keydown', keydown)
  }, [])

  const submit = async (event: FormEvent) => {
    event.preventDefault()
    if (submitState !== 'idle') return
    const next: Record<string, string> = {}
    if (!name.trim()) next.name = 'Please enter your full name.'
    if (!company.trim()) next.company = 'Please enter your company name.'
    if (!validWorkEmail(email)) next.email = 'Please use your company or work email address.'
    if (enquiry.kind !== 'team' && !role.trim()) next.role = 'Please enter a role or job title.'
    if (enquiry.kind === 'team' && !teamFocus.trim()) next.teamFocus = 'Please enter your team focus.'
    if (selected.includes('Other') && !otherDepartment.trim()) next.otherDepartment = 'Please describe the department.'
    if (enquiry.kind === 'drive' && expectedCandidates) {
      const counts = expectedCandidates.trim().split(/\s*-\s*/).map(Number)
      if (!/^\d+(?:\s*-\s*\d+)?$/.test(expectedCandidates.trim()) || counts.some(count => !Number.isInteger(count) || count < 1 || count > 100000) || (counts.length === 2 && counts[0] > counts[1])) next.expectedCandidates = 'Enter a count or range, e.g. 10-20 (1 to 100,000).'
    }
    if (howSoon === 'Other' && !otherTiming.trim()) next.otherTiming = 'Please describe your timeline.'
    if (!selected.length) next.departments = 'Please select at least one department.'
    if (!Number.isInteger(Number(headcount)) || Number(headcount) < 1 || Number(headcount) > 10000) next.headcount = 'Enter a whole number between 1 and 10,000.'
    if (enquiry.kind === 'drive' && !location.trim()) next.location = 'Please enter a hiring location.'
    if (enquiry.kind === 'drive' && (!deadline || deadline < minimumDate)) next.deadline = 'Choose today or a future date.'
    setErrors(next)
    if (Object.keys(next).length) return
    const body = new FormData()
    body.set('kind', enquiry.kind)
    body.set('full_name', name.trim())
    body.set('company', company.trim())
    body.set('work_email', email.trim())
    if (selfDescription.trim()) body.set('self_description', selfDescription === 'Other' ? otherDescription.trim() || 'Other' : selfDescription.trim())
    if (enquiry.kind === 'team') body.set('team_focus', teamFocus.trim())
    else body.set('role', role.trim())
    body.set('location', location.trim())
    if (enquiry.kind === 'drive') body.set('deadline', deadline)
    body.set('headcount', String(headcount))
    selected.forEach(department => body.append('departments', department))
    body.set('notes', enquiry.kind === 'team' ? [teamStage, notes.trim()].filter(Boolean).join('\n') : enquiry.kind === 'drive' ? [`Drive format: ${driveMode}`, expectedCandidates ? `Expected candidates for the drive: ${expectedCandidates}` : '', notes.trim()].filter(Boolean).join('\n') : notes.trim())
    if (howSoon) body.set('how_soon', howSoon)
    if (selected.includes('Other')) body.set('other_department', otherDepartment.trim())
    if (howSoon === 'Other') body.set('how_soon_details', otherTiming.trim())
    if (file) body.set('jd', file)
    setSubmitState('sending')
    setSubmitError('')
    try {
      await api.submitHiringEnquiry(body)
      setSubmitState('sent')
    } catch (error) {
      setSubmitState('idle')
      setSubmitError(error instanceof Error ? error.message : 'Your request could not be sent. Please try again.')
    }
  }

  const field = (key: string, label: string, value: string, change: (value: string) => void, type = 'text') => <label className={`enquiry-field${key === 'selfDescription' ? ' enquiry-field--description' : ''}`}>
    <span className={['name', 'company', 'email', 'role', 'location', 'selfDescription'].includes(key) ? 'enquiry-field__visually-hidden' : undefined}>{label}</span><input type={type} value={value} placeholder={label} maxLength={key === 'selfDescription' ? 240 : undefined} onChange={event => change(event.target.value)} aria-invalid={!!errors[key]} aria-describedby={errors[key] ? `${titleId}-${key}-error` : undefined} />
    {errors[key] && <small id={`${titleId}-${key}-error`} className="enquiry-error">{errors[key]}</small>}
  </label>

  const departmentField = <fieldset className={`enquiry-departments enquiry-departments--${enquiry.kind}`}>
    <legend>{details.department}</legend>
    <div className="enquiry-pills">{departments.filter(department => department !== 'Other').map(department => <button key={department} type="button" aria-pressed={selected.includes(department)} onClick={() => setSelected(current => current.includes(department) ? current.filter(item => item !== department) : [...current, department])}>{department}</button>)}<input className="enquiry-other-input" aria-label="Which departments?" placeholder="Which departments?" maxLength={160} value={otherDepartment} onChange={event => { const value = event.target.value; setOtherDepartment(value); setSelected(current => value.trim() ? [...current.filter(item => item !== 'Other'), 'Other'] : current.filter(item => item !== 'Other')) }} /></div>{errors.otherDepartment && <small className="enquiry-error">{errors.otherDepartment}</small>}
    {enquiry.kind === 'team' && selected.length > 1 && <p className="enquiry-summary">Selected: {selected.join(', ')}</p>}
    {errors.departments && <small className="enquiry-error" role="alert">{errors.departments}</small>}
  </fieldset>

  const headcountField = <div className="enquiry-headcount">
    <div className="enquiry-headcount__heading"><label htmlFor={`${titleId}-count`}>{enquiry.kind === 'drive' ? 'Number of openings' : 'Headcount'}</label><span>{headcount || '0'} openings</span></div>
    <input aria-label="Headcount slider" type="range" min="1" max="10" value={Math.min(10, Math.max(1, Number(headcount) || 1))} onChange={event => setHeadcount(event.target.value)} />
    <div className="enquiry-headcount__scale"><span>1</span><span>10</span></div>
    <label className="enquiry-count-input">Exact openings <input id={`${titleId}-count`} type="number" min="1" max="10000" step="1" value={headcount} onChange={event => setHeadcount(event.target.value)} aria-invalid={!!errors.headcount} /></label>
    {errors.headcount && <small className="enquiry-error" role="alert">{errors.headcount}</small>}
  </div>

  const chooseFile = (chosen: File | null) => {
    if (chosen && !/\.(pdf|docx)$/i.test(chosen.name)) {
      setErrors(current => ({ ...current, file: 'Choose a PDF or DOCX file.' }))
      setFile(null)
      return
    }
    setErrors(current => { const next = { ...current }; delete next.file; return next })
    setFile(chosen)
  }

  const uploadField = <div className={`enquiry-upload${dragging ? ' is-dragging' : ''}`}
    onDragOver={event => { event.preventDefault(); setDragging(true) }}
    onDragLeave={() => setDragging(false)}
    onDrop={event => { event.preventDefault(); setDragging(false); chooseFile(event.dataTransfer.files[0] ?? null) }}>
    <input ref={fileRef} id={`${titleId}-file`} aria-label={file ? "Replace JD's" : "Upload JD's"} type="file" accept=".pdf,.docx,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document" onChange={event => { chooseFile(event.target.files?.[0] ?? null); event.target.value = '' }} />
    <label htmlFor={`${titleId}-file`}><Paperclip size={18} aria-hidden="true" /><span>{enquiry.kind === 'team' ? 'Upload JD(s) for all the open hiring positions' : 'Upload JD(s)'}<small>Click to upload or drag and drop · PDF or DOCX</small></span></label>
    {file && <div className="enquiry-upload__file"><span>{file.name}</span><button type="button" onClick={() => { setFile(null); if (fileRef.current) fileRef.current.value = '' }}>Remove</button></div>}
    {errors.file && <small className="enquiry-error" role="alert">{errors.file}</small>}
  </div>

  return createPortal(<div className={`enquiry-backdrop${closing ? ' is-closing' : ''}`} onMouseDown={event => { if (event.target === event.currentTarget) close() }}>
    <div className={`enquiry-scene${enquiry.showStats ? ' enquiry-scene--stats' : ''}`} onMouseDown={event => { if (event.target === event.currentTarget) close() }}>
    {enquiry.showStats && <aside className="enquiry-stats" aria-label="Hiring with enter"><div className="enquiry-stats__items"><div><strong>24 Hours</strong><span>High-signal profiles, delivered.</span></div><div><strong>3 Candidates</strong><span>Curated for quality, not quantity.</span></div><div><strong>10 Days</strong><span>Average time to hire</span></div></div></aside>}
    <div ref={panelRef} className={`enquiry-drawer enquiry-drawer--${enquiry.kind}`} role="dialog" aria-modal="true" aria-labelledby={titleId}>
      <header className="enquiry-header"><div><h2 id={titleId}>{details.title}</h2><p>{details.description}</p>{enquiry.kind === 'hire' && (role || editingContext) && <div className="enquiry-context"><span>I'm looking for a {editingContext ? <input aria-label="Role or job title" value={role} maxLength={180} style={{ width: `${Math.max(4, role.length)}ch` }} onChange={event => setRole(event.target.value)} /> : <span className="enquiry-context__value">{role}</span>} in {editingContext ? <input aria-label="Hiring location" value={location} maxLength={180} style={{ width: `${Math.max(4, location.length)}ch` }} onChange={event => setLocation(event.target.value)} /> : <span className="enquiry-context__value">{location}</span>}.</span><button type="button" aria-label={editingContext ? 'Done editing hiring details' : 'Edit hiring details'} onClick={() => setEditingContext(value => !value)}>{editingContext ? 'Done' : 'Edit'}</button></div>}{enquiry.kind === 'team' && <div className="enquiry-context"><span>I'm building a {editingContext ? <input aria-label="Team focus" value={teamFocus} style={{ width: `${Math.max(4, teamFocus.length)}ch` }} onChange={event => setTeamFocus(event.target.value)} /> : <span className="enquiry-context__value">{teamFocus}</span>} team of {editingContext ? <input aria-label="Team size" type="number" min="1" max="10000" value={headcount} onChange={event => setHeadcount(event.target.value)} /> : <span className="enquiry-context__value">{headcount}</span>} people in {editingContext ? <input aria-label="Team location" placeholder="Location" value={location} maxLength={180} style={{ width: `${Math.max(4, location.length)}ch` }} onChange={event => setLocation(event.target.value)} /> : <span className="enquiry-context__value">{location || 'your location'}</span>}.</span><button type="button" aria-label={editingContext ? 'Done editing hiring details' : 'Edit hiring details'} onClick={() => setEditingContext(value => !value)}>{editingContext ? 'Done' : 'Edit'}</button></div>}{enquiry.kind === 'drive' && <div className="enquiry-context"><span>I am looking for {editingContext ? <input aria-label="Drive role" value={role} style={{ width: `${Math.max(4, role.length)}ch` }} maxLength={180} onChange={event => setRole(event.target.value)} /> : <span className="enquiry-context__value">{role}</span>} in {editingContext ? <input aria-label="Drive location" value={location} style={{ width: `${Math.max(4, location.length)}ch` }} maxLength={180} onChange={event => setLocation(event.target.value)} /> : <span className="enquiry-context__value">{location}</span>} by {editingContext ? <input aria-label="Drive date" type="date" min={minimumDate} value={deadline} onChange={event => setDeadline(event.target.value)} /> : <span className="enquiry-context__value">{deadline ? new Date(`${deadline}T00:00:00`).toLocaleDateString('en-GB', { day: 'numeric', month: 'long' }) : 'your target date'}</span>}.</span><button type="button" aria-label={editingContext ? 'Done editing hiring details' : 'Edit hiring details'} onClick={() => setEditingContext(value => !value)}>{editingContext ? 'Done' : 'Edit'}</button></div>}</div><button ref={closeRef} className="enquiry-close" type="button" onClick={close} aria-label="Close hiring enquiry"><X size={14} aria-hidden="true" /></button></header>
      <form className="enquiry-form" noValidate onSubmit={submit}>
        {field('name', 'Your name', name, setName)}
        {field('company', 'Company name', company, setCompany)}
        {field('email', 'Work email', email, setEmail, 'email')}
        <div className="enquiry-field enquiry-description-dropdown"><details onBlur={event => { if (!event.currentTarget.contains(event.relatedTarget)) event.currentTarget.open = false }} onKeyDown={event => { if (event.key === 'Escape' && event.currentTarget.open) { event.stopPropagation(); event.currentTarget.open = false; event.currentTarget.querySelector('summary')?.focus() } }}><summary aria-label="What best describes you?"><span className={selfDescription ? 'has-value' : ''}>{selfDescription || 'What best describes you?'}</span><ChevronDown size={14} strokeWidth={1.5} aria-hidden="true" /></summary><div className="enquiry-description-menu">{['Founder', 'HR/TA', 'Founding team', 'Leadership', 'Other'].map(option => <button type="button" key={option} aria-pressed={selfDescription === option} onClick={event => { setSelfDescription(option); const dropdown = event.currentTarget.closest('details'); if (dropdown) { dropdown.open = false; dropdown.querySelector('summary')?.focus() } }}>{option}</button>)}</div></details>{selfDescription === 'Other' && <input autoFocus aria-label="Describe your role" placeholder="Please describe your role" maxLength={240} value={otherDescription} onChange={event => setOtherDescription(event.target.value)} />}</div>
        {enquiry.kind === 'hire' && <>{!enquiry.role && field('role', 'Role or job title', role, setRole)}{!enquiry.location && field('location', 'Hiring location', location, setLocation)}{departmentField}{!enquiry.headcount && headcountField}</>}
        {enquiry.kind === 'team' && <>{!enquiry.teamFocus && field('teamFocus', 'Team or department focus', teamFocus, setTeamFocus)}{departmentField}{!enquiry.headcount && headcountField}</>}
        {enquiry.kind === 'drive' && <>{departmentField}{!enquiry.role && field('role', 'Role or job title', role, setRole)}{!enquiry.headcount && headcountField}{!enquiry.location && field('location', 'Hiring location', location, setLocation)}{!enquiry.deadline && <label className="enquiry-field"><span>Target hiring date</span><input type="date" min={minimumDate} value={deadline} onChange={event => setDeadline(event.target.value)} aria-invalid={!!errors.deadline} />{errors.deadline && <small className="enquiry-error" role="alert">{errors.deadline}</small>}</label>}</>}
        {enquiry.kind === 'team' ? <fieldset className="enquiry-timing"><legend>Where is this team?</legend><div className="enquiry-pills">{['A brand-new team', 'Scaling an existing team', 'Rebuilding a team'].map(option => <button key={option} type="button" aria-pressed={teamStage === option} onClick={() => setTeamStage(option)}>{option}</button>)}</div></fieldset> : enquiry.kind === 'drive' ? <div className="enquiry-drive-details"><fieldset className="enquiry-timing"><legend>How will the drive run?</legend><div className="enquiry-pills">{['In person', 'Online'].map(option => <button key={option} type="button" aria-pressed={driveMode === option} onClick={() => setDriveMode(option)}>{option}</button>)}</div></fieldset><label className="enquiry-field"><span>Expected candidates for the drive</span><input type="text" inputMode="text" maxLength={20} placeholder="eg. 10-20" value={expectedCandidates} onChange={event => setExpectedCandidates(event.target.value)} aria-invalid={!!errors.expectedCandidates} />{errors.expectedCandidates && <small className="enquiry-error" role="alert">{errors.expectedCandidates}</small>}</label></div> : <fieldset className="enquiry-timing"><legend>How soon do you wish to close this position?</legend><div className="enquiry-pills">{['2 weeks', '30 days'].map(option => <button key={option} type="button" aria-pressed={howSoon === option} onClick={() => { setHowSoon(option); setOtherTiming('') }}>{option}</button>)}<input className="enquiry-other-input" aria-label="Your timeline" placeholder="Your timeline" maxLength={120} value={otherTiming} onChange={event => { setOtherTiming(event.target.value); setHowSoon(event.target.value.trim() ? 'Other' : '') }} /></div>{errors.otherTiming && <small className="enquiry-error">{errors.otherTiming}</small>}</fieldset>}
        <label className="enquiry-field"><span>Notes</span><textarea aria-label="Notes" rows={2} maxLength={250} aria-describedby={`${titleId}-notes-limit`} placeholder="Anything else we should know to help you hire better?" value={notes} onChange={event => setNotes(event.target.value.slice(0, 250))} /><small id={`${titleId}-notes-limit`} className="enquiry-notes-limit">{notes.length}/250 characters</small></label>
        {uploadField}
        {submitState === 'sent' && <p className="enquiry-notice" role="status">Thank you. Your request has been received. Our team will follow up at your work email.</p>}
        {submitError && <p className="enquiry-notice enquiry-notice--error" role="alert">{submitError}</p>}
        <div className="enquiry-actions"><button type="submit" className="enquiry-submit" disabled={submitState !== 'idle'}>{submitState === 'sending' ? 'Sending…' : submitState === 'sent' ? 'Sent' : details.action} </button><small>We’ll be in touch within 24 hours<br />Your details remain confidential.</small></div>
      </form>
    </div>
    </div>
  </div>, document.body)
}
