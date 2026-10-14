import { useEffect, useRef, useState } from 'react'
import type { FormEvent } from 'react'
import { api } from '../api'
import type { Candidate, CareerPreferences, WorkExperience } from '../types'
import { CandidateProcessing } from './CandidatePresentation'
import CandidateCareerTimeline from './CandidateCareerTimeline'
import CandidateResumePreview from './CandidateResumePreview'
import EnterBrandText from './EnterBrandText'
import { professionalTitle } from '../candidateIdentity'
import { UserRound, Settings, GraduationCap, BriefcaseBusiness, MapPin, Camera, Trash2, Clock3, BadgeIndianRupee, House, Phone, Link2, FileText, Target, Globe2, Pencil } from 'lucide-react'
import './candidate-experience.css'

const motivators = ['Exceptional team', 'Harder problems', 'More ownership', 'Compensation', 'Founding team', 'Leadership', 'Product', 'Global exposure', 'Founder']
const exclusions = ['5-day WFO', 'Services companies', 'Pure management', 'Java roles', 'Below ₹50L', 'Large companies']
const noticePeriods = [0, 15, 30, 45, 60, 90]
const employmentTypes = ['Full-time', 'Part-time', 'Contract', 'Internship']
const workSetups = ['Hybrid', 'On-site', 'Remote']
const contactMethods = ['Email', 'WhatsApp', 'Phone']
function LinkedInIcon() {
  return <svg viewBox="0 0 24 24" aria-hidden="true"><path fill="currentColor" d="M5.2 8.3A1.85 1.85 0 1 0 5.2 4.6a1.85 1.85 0 0 0 0 3.7ZM3.6 9.8h3.2V20H3.6V9.8ZM9 9.8h3.1v1.5h.05c.44-.82 1.5-1.7 3.1-1.7 3.3 0 3.9 2.18 3.9 5V20H16v-4.75c0-1.13-.02-2.58-1.58-2.58-1.58 0-1.82 1.23-1.82 2.5V20H9V9.8Z" /></svg>
}
const list = (text: string) => [...new Set(text.split(/[,\n]/).map(value => value.trim()).filter(Boolean))]
const label = (key: string) => key.replaceAll('_', ' ')
const displayName = (name: string) => name === name.toLocaleUpperCase() ? name.toLocaleLowerCase().replace(/(^|[\s-])\p{L}/gu, letter => letter.toLocaleUpperCase()) : name
const collegeName = (education: string[]) => {
  const entry = education.find(value => value.trim())?.trim()
  if (!entry) return ''
  return entry.split(/\s+[—–-]\s+|,\s*(?=(?:B(?:Tech|E|Sc|CA)\b|M(?:Tech|E|Sc|CA|BA)\b|Bachelor|Master|Diploma|PhD|Doctor))/i)[0]?.trim() || entry
}
const concise = (value: string, limit = 420) => value.length <= limit ? value : `${value.slice(0, limit).replace(/\s+\S*$/, '')}…`
function enterRead(profile: Candidate, strongest: string[]) {
  const savedSummary = profile.summary?.trim() || ''
  if (savedSummary) return concise(savedSummary)
  const roles = [...(profile.work_experiences || [])].filter(item => item.role || item.company).sort((a, b) => (a.start_date || '').localeCompare(b.start_date || ''))
  if (!roles.length) return 'Add a short professional summary using “Not quite — edit”.'
  const first = roles[0], latest = roles.at(-1)!
  const employers = new Set(roles.map(item => item.company).filter(Boolean)).size
  const progression = first.role && latest.role && first.role !== latest.role
    ? `Your saved career history progresses from ${first.role} to ${latest.role}`
    : `Your saved profile shows experience as ${latest.role || 'a professional'}`
  const companyContext = employers ? ` across ${employers} ${employers === 1 ? 'employer' : 'employers'}` : ''
  const strengths = strongest.length ? `. Your recorded strengths include ${strongest.slice(0, 3).join(', ')}` : ''
  return `${progression}${companyContext}${strengths}.`
}

function CandidatePhoto({ profile, busy, upload, remove }: { profile: Candidate; busy: boolean; upload: (file: File) => void; remove: () => void }) {
  const [source, setSource] = useState('')
  useEffect(() => {
    if (!profile.profile_photo_url) return
    let active = true
    let objectUrl = ''
    api.candidatePhoto().then(blob => {
      if (!active) return
      objectUrl = URL.createObjectURL(blob)
      setSource(objectUrl)
    }).catch(() => { /* keep the private initials fallback */ })
    return () => { active = false; if (objectUrl) URL.revokeObjectURL(objectUrl) }
  }, [profile.profile_photo_url])
  const available = Boolean(source)
  const initials = (profile.full_name || '').split(/\s+/).filter(Boolean).map(part => part[0]).join('').slice(0, 2).toLocaleUpperCase() || 'E'
  return <div className="cp-photo-control">
    <div className="cp-photo" aria-label={available ? `${profile.full_name} profile photo` : `${profile.full_name} initials`}>
      {available ? <img src={source} alt={`${profile.full_name} profile`} /> : <span aria-hidden="true">{initials}</span>}
    </div>
    <div className="cp-photo-actions"><label><Camera size={14} aria-hidden="true" />{profile.profile_photo_url ? 'Replace' : 'Add photo'}<input type="file" accept="image/jpeg,image/png,image/webp" disabled={busy} onChange={event => { const file = event.target.files?.[0]; if (file) upload(file); event.target.value = '' }} /></label>{profile.profile_photo_url && <button type="button" disabled={busy} onClick={remove}><Trash2 size={14} aria-hidden="true" />Remove</button>}</div>
  </div>
}

function BuildLeadSpectrum({ value, save }: { value: number | null; save: (value: number) => Promise<boolean> }) {
  const [draft, setDraft] = useState(value ?? 50)
  const [dirty, setDirty] = useState(false)
  const saveRef = useRef(save)
  useEffect(() => { saveRef.current = save }, [save])
  useEffect(() => {
    if (!dirty) return
    const timer = window.setTimeout(() => { void saveRef.current(draft).then(ok => { if (ok) setDirty(false) }) }, 500)
    return () => window.clearTimeout(timer)
  }, [draft, dirty])
  const positions = ['Mostly hands-on', 'Hands-on + technical leadership', '50/50', 'Mostly team leadership', 'People leadership']
  const description = positions[Math.round(draft / 25)]
  return <section className="cp-spectrum" aria-labelledby="build-lead-heading">
    <div><h3 id="build-lead-heading">Build + Lead Spectrum</h3><p>{value === null && !dirty ? 'Choose how you want your next role to feel.' : description}</p></div>
    <div className="cp-spectrum-control"><input type="range" min="0" max="100" step="25" value={draft} aria-label="Build and Lead preference" aria-valuetext={description} onChange={event => { setDraft(Number(event.target.value)); setDirty(true) }} /><div className="cp-spectrum-labels" aria-hidden="true">{positions.map(position => <span key={position}>{position}</span>)}</div></div>
  </section>
}

function Chips({ options, selected, onChange, disabled = false }: { options: string[]; selected: string[]; onChange: (value: string[]) => Promise<boolean>; disabled?: boolean }) {
  const [glowing, setGlowing] = useState<string | null>(null)
  const [optimistic, setOptimistic] = useState<string[] | null>(null)
  return <div className="cp-chips">{[...new Set(options)].map(option => <button type="button" key={option} disabled={disabled} className={glowing === option ? 'cp-chip-glow' : undefined} onAnimationEnd={() => setGlowing(null)} aria-pressed={(optimistic ?? selected).includes(option)} onClick={async () => { const removing = selected.includes(option); const next = removing ? selected.filter(value => value !== option) : [...selected, option]; setGlowing(removing ? null : option); setOptimistic(next); await onChange(next); setOptimistic(null) }}>{option}</button>)}</div>
}

function CustomChoice({ label, disabled, add }: { label: string; disabled: boolean; add: (value: string) => Promise<boolean> }) {
  const [open, setOpen] = useState(false)
  const [value, setValue] = useState('')
  return open ? <form className="cp-actions cp-custom-exclusion" onSubmit={async event => { event.preventDefault(); if (value.trim() && await add(value.trim())) { setValue(''); setOpen(false) } }}><label>{label}<input autoFocus maxLength={240} value={value} onChange={event => setValue(event.target.value)} required /></label><button disabled={disabled}>Add option</button><button type="button" onClick={() => setOpen(false)}>Cancel</button></form> : <button className="cp-add-choice" type="button" onClick={() => setOpen(true)}>+ Add my own</button>
}

function ProfileEditor({ profile, save, cancel, busy }: { profile: Candidate; save: (patch: Partial<Candidate>) => Promise<boolean>; cancel: () => void; busy: boolean }) {
  const [rows, setRows] = useState(profile.work_experiences)
  const update = (index: number, patch: Partial<WorkExperience>) => setRows(previous => previous.map((row, i) => i === index ? { ...row, ...patch } : row))
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const data = new FormData(event.currentTarget)
    const get = (key: string) => String(data.get(key) || '').trim()
    const patch: Partial<Candidate> = {
      full_name: get('full_name'), headline: get('headline'), current_company: get('current_company'),
      location: get('location'), total_experience: get('total_experience') || '0',
      summary: get('summary'), skills: list(get('skills')), education: get('education').split('\n').map(s => s.trim()).filter(Boolean),
      work_experiences: rows.map(row => ({ ...row, start_date: row.start_date || null, end_date: row.end_date || null, date_label: row.date_label || (!row.end_date ? `${row.start_date || 'Start not specified'} — End not specified` : '') })),
      career_preferences: { strongest_skills: list(get('strongest_skills')), standout_signal: get('standout_signal'), likely_directions: profile.career_preferences?.likely_directions ?? [] },
    }
    if (await save(patch)) cancel()
  }
  return <form className="cp-editor" onSubmit={submit}>
    <header className="cp-editor-heading"><div><h3>Edit your profile</h3><p>Review your resume details and correct anything that needs updating.</p></div><button type="button" disabled={busy} onClick={cancel}>Cancel</button></header>
    <fieldset disabled={busy}><section className="cp-editor-section" aria-labelledby="profile-details-heading"><h4 id="profile-details-heading">Profile details</h4><div className="cp-fields cp-profile-fields">
      {(['full_name', 'headline', 'current_company', 'location', 'total_experience'] as const).map(key => <label className={key === 'headline' ? 'cp-field-wide' : undefined} key={key}>{{ full_name: 'Full name', headline: 'Professional title', current_company: 'Current company', location: 'Location', total_experience: 'Experience (years)' }[key]}<input name={key} defaultValue={key === 'headline' ? professionalTitle(profile) : profile[key]} type={key === 'total_experience' ? 'number' : 'text'} min={0} step="0.1" required={key === 'full_name'} /></label>)}
    </div></section>
    <section className="cp-editor-section" aria-labelledby="profile-strengths-heading"><h4 id="profile-strengths-heading">Skills &amp; highlights</h4><div className="cp-fields cp-profile-fields">
      <label>All skills<input name="skills" defaultValue={profile.skills.join(', ')} /></label>
      <label>Strongest skills (up to five)<input name="strongest_skills" defaultValue={(profile.career_preferences?.strongest_skills ?? profile.skills.slice(0, 5)).join(', ')} /></label>
      <label>Standout signal<textarea name="standout_signal" rows={3} maxLength={1000} placeholder="An achievement from your resume (optional)" defaultValue={profile.career_preferences?.standout_signal || ''} /></label>
      <label>ENTER's read on you<textarea name="summary" rows={3} maxLength={1200} placeholder="Your professional summary (optional)" defaultValue={profile.summary} /></label>
    </div></section>
    <section className="cp-editor-section" aria-labelledby="profile-education-heading"><h4 id="profile-education-heading">Education</h4><div className="cp-fields cp-profile-fields">
      <label className="cp-field-wide">Education (one entry per line)<textarea name="education" defaultValue={profile.education.join('\n')} /></label>
    </div></section>
    <section className="cp-editor-section cp-history-editor" aria-labelledby="career-history-heading"><div className="cp-editor-section-heading"><div><h4 id="career-history-heading">Resume-extracted career history</h4><p>This came from your uploaded resume. Open only a role that needs correcting.</p></div></div>
    {rows.map((row, i) => {
      const period = row.date_label || `${row.start_date || 'Start not specified'} — ${row.end_date || 'End not specified'}`
      return <details className="cp-work-edit" key={i}><summary><span><strong>{row.role || 'Role not specified'}</strong><small>{row.company || 'Employer not specified'} · {period}</small></span><span className="cp-role-edit"><Pencil aria-hidden="true" />Edit</span></summary><div className="cp-work-edit-fields">
        <label>Company<input required value={row.company} onChange={e => update(i, { company: e.target.value })} /></label>
        <label>Job title<input required value={row.role} onChange={e => update(i, { role: e.target.value })} /></label>
        <label>Start date<input type="date" value={row.start_date || ''} onChange={e => update(i, { start_date: e.target.value || null, date_label: /present|current|now/i.test(row.date_label || '') ? `${e.target.value || 'Start not specified'} — Present` : '' })} /></label>
        <label>End date<input type="date" value={row.end_date || ''} onChange={e => update(i, { end_date: e.target.value || null, date_label: '' })} /></label>
        <label className="cp-check"><input type="checkbox" checked={/present|current|now/i.test(row.date_label || '') && !row.end_date} onChange={e => update(i, { end_date: e.target.checked ? null : row.end_date, date_label: e.target.checked ? `${row.start_date || 'Start not specified'} — Present` : '' })} />Current role</label>
        <label>Career gap context<input value={row.gap_reason} onChange={e => update(i, { gap_reason: e.target.value })} /></label>
        <label className="cp-field-wide">Role details<textarea value={row.description} onChange={e => update(i, { description: e.target.value })} /></label>
      </div></details>
    })}
    </section><div className="cp-actions cp-editor-actions"><span>Changes apply when you save.</span><button className="primary" type="submit">Save corrections</button></div>
    </fieldset></form>
}

const isExperienceList = (value: unknown): value is WorkExperience[] => Array.isArray(value) && value.every(item => (
  typeof item === 'object' && item !== null && 'company' in item && 'role' in item
))

function ExperienceReviewList({ items }: { items: WorkExperience[] }) {
  return <ol className="cp-review-history">{items.map((item, index) => {
    const period = item.date_label || `${item.start_date || 'Start not specified'} — ${item.end_date || 'End not specified'}`
    return <li key={`${item.company}-${item.role}-${item.start_date || index}`}><strong>{item.role || 'Role not specified'}</strong><span>{item.company || 'Employer not specified'}</span><small>{period}</small></li>
  })}</ol>
}

function ResumeReview({ profile, apply, busy }: { profile: Candidate; apply: (fields: string[]) => void; busy: boolean }) {
  const [selected, setSelected] = useState<string[]>([])
  if (!profile.resume_review) return null
  const display = (value: unknown) => Array.isArray(value) ? value.map(String).join('\n') : String(value ?? 'Not specified')
  const proposedHistory = profile.resume_review.fields.work_experiences
  const historySummary = isExperienceList(proposedHistory) ? `${proposedHistory.length} roles across ${new Set(proposedHistory.map(item => item.company)).size} employers` : ''
  return <details className="cp-resume-updates"><summary>New resume changes to review ({Object.keys(profile.resume_review.fields).length})</summary><p className="cp-muted">Your profile is already available. These are only fields from the latest resume that conflict with saved corrections; choose what to update, or leave your profile unchanged.</p>
    {historySummary && <p className="cp-review-summary"><strong>Career Journey:</strong> your saved profile has {profile.work_experiences.length} roles; the latest resume contains {historySummary}.</p>}
    {Object.entries(profile.resume_review.fields).map(([key, value]) => {
      const history = key === 'work_experiences' && isExperienceList(value)
      const savedHistory = history && isExperienceList(profile.work_experiences) ? profile.work_experiences : []
      return <details key={key} className="cp-review-field" open={history}><summary>{history ? 'Career Journey roles' : label(key)}</summary><div className="cp-fields"><div><small>Saved profile</small>{history ? <ExperienceReviewList items={savedHistory} /> : <p>{display(profile[key as keyof Candidate])}</p>}</div><div><small>Latest resume</small>{history ? <ExperienceReviewList items={value} /> : <p>{display(value)}</p>}</div></div><label className="cp-check"><input type="checkbox" checked={selected.includes(key)} disabled={busy} onChange={e => setSelected(e.target.checked ? [...selected, key] : selected.filter(item => item !== key))} />{history ? `Use these ${value.length} roles in my Career Journey` : `Replace ${label(key)}`}</label></details>
    })}
    <div className="cp-actions"><button className="primary" disabled={busy || !selected.length} onClick={() => apply(selected)}>Apply selected changes</button><button disabled={busy} onClick={() => apply([])}>Keep my saved profile</button></div>
  </details>
}

export default function CandidateExperience({ beforeLeaveRef }: { accountDeleted?: () => void; beforeLeaveRef?: React.MutableRefObject<(() => Promise<boolean>) | null> }) {
  const [profile, setProfile] = useState<Candidate | null>(null)
  const [settingsOpen, setSettingsOpen] = useState(false)
  const [error, setError] = useState('')
  const [message, setMessage] = useState('')
  const [busy, setBusy] = useState(false)
  const busyRef = useRef(false)
  const [editing, setEditingState] = useState(false)
  function setEditing(value: boolean) {
    setEditingState(value)
    if (value) {
      setSettingsOpen(false)
      setReview(false)
    }
  }
  const [editingSettings, setEditingSettings] = useState(false)
  const [editingSettingsField, setEditingSettingsField] = useState('availability')
  const [showBeyond, setShowBeyond] = useState(false)
  const [review, setReview] = useState(false)
  const [success, setSuccess] = useState(false)
  const [successAnimationComplete, setSuccessAnimationComplete] = useState(false)
  const [footerPanel, setFooterPanel] = useState<'support' | null>(null)
  const [dragging, setDragging] = useState(false)
  const [pollError, setPollError] = useState('')
  const mainRef = useRef<HTMLElement>(null)
  const wasProcessing = useRef(false)
  const focusUpload = useRef(false)
  const [meaningfulDraft, setMeaningfulDraft] = useState<string | null>(null)
  const answerDraft = useRef<string | null>(null)
  const draftStorageKey = useRef('')
  const answerFlight = useRef<Promise<boolean> | null>(null)
  const answerTimer = useRef<ReturnType<typeof setTimeout> | undefined>(undefined)
  const answerInput = useRef<HTMLTextAreaElement>(null)
  const [answerError, setAnswerError] = useState(false)
  const writeQueue = useRef<Promise<unknown>>(Promise.resolve())
  const writes = useRef(0)
  async function run(action: () => Promise<Candidate>, notice = 'Saved.', quiet = false) {
    if (!quiet) writes.current++
    busyRef.current = true; setBusy(writes.current > 0)
    const operation = writeQueue.current.then(async () => {
      setError(''); setMessage('')
      try { setProfile(await action()); setMessage(notice); return true }
      catch (cause) { setError(cause instanceof Error ? cause.message : 'Could not save. Please try again.'); return false }
      finally { if (!quiet) writes.current--; busyRef.current = writes.current > 0; setBusy(writes.current > 0) }
    })
    writeQueue.current = operation
    return operation
  }
  function flushAnswer(): Promise<boolean> {
    clearTimeout(answerTimer.current)
    if (answerFlight.current) return answerFlight.current
    const operation = (async () => {
      while (answerDraft.current !== null) {
        const value = answerDraft.current
        if (!await run(() => api.updateCandidate({ meaningful_work: value }), 'Answer saved.', true)) {
          setAnswerError(true); return false
        }
        setAnswerError(false)
        // A newer draft stays visible and is saved next, never replaced by an older response.
        if (answerDraft.current === value) {
          answerDraft.current = null; setMeaningfulDraft(null)
          try { sessionStorage.removeItem(draftStorageKey.current) } catch { /* beforeunload still guards unsaved text when storage is unavailable */ }
        }
      }
      return true
    })()
    answerFlight.current = operation
    void operation.finally(() => { answerFlight.current = null })
    return operation
  }
  function leave(action: () => void) {
    if (answerDraft.current === null && !answerFlight.current) { action(); return }
    void flushAnswer().then(saved => { if (saved) action() })
  }
  function toggleSettings(preserveSuccess = false) {
    void leave(() => {
      setSettingsOpen(open => !open)
      setEditingSettings(false); setReview(false); if (!preserveSuccess) setSuccess(false)
    })
  }
  function changeAnswer(value: string) {
    answerDraft.current = value; setMeaningfulDraft(value)
    // Tab-local and account-scoped: recover an unsaved answer after session expiry
    // without exposing it to another signed-in candidate or retaining saved answers.
    try { if (draftStorageKey.current) sessionStorage.setItem(draftStorageKey.current, value) } catch { /* storage may be disabled */ }
    clearTimeout(answerTimer.current)
    answerTimer.current = setTimeout(() => { void flushAnswer() }, 650)
  }
  useEffect(() => {
    const warn = (event: BeforeUnloadEvent) => {
      if (answerDraft.current !== null) { event.preventDefault(); event.returnValue = '' }
    }
    window.addEventListener('beforeunload', warn)
    return () => { window.removeEventListener('beforeunload', warn); clearTimeout(answerTimer.current) }
  }, [])
  useEffect(() => {
    if (beforeLeaveRef) beforeLeaveRef.current = flushAnswer
    return () => { if (beforeLeaveRef) beforeLeaveRef.current = null }
  })
  useEffect(() => {
    const input = answerInput.current
    if (input) { input.style.height = 'auto'; input.style.height = `${Math.max(62, input.scrollHeight)}px` }
  }, [meaningfulDraft, profile?.meaningful_work, showBeyond, settingsOpen])
  useEffect(() => {
    let active = true
    api.candidateProfile().then(data => {
      if (!active) return
      setProfile(data)
      draftStorageKey.current = `enter:candidate:${data.id}:answer-draft`
      try {
        const draft = sessionStorage.getItem(draftStorageKey.current)
        if (draft !== null && draft !== data.meaningful_work) {
          answerDraft.current = draft; setMeaningfulDraft(draft); setAnswerError(true); setShowBeyond(true)
        } else sessionStorage.removeItem(draftStorageKey.current)
      } catch { /* storage may be disabled */ }
    }).catch(cause => { if (active) setError(cause.message) })
    return () => { active = false }
  }, [])
  const status = profile?.latest_resume?.processing_status
  const processing = status === 'uploaded' || status === 'queued' || status === 'processing'
  const resumeId = profile?.latest_resume?.id
  useEffect(() => {
    if (processing || wasProcessing.current || focusUpload.current) {
      const target = mainRef.current?.querySelector<HTMLElement>('.processing-card, .cp-section')
      target?.focus({ preventScroll: true })
      target?.scrollIntoView?.({ block: 'start', behavior: 'instant' })
    }
    wasProcessing.current = processing
    focusUpload.current = false
  }, [processing, resumeId])
  useEffect(() => {
    if (!processing) return
    let active = true
    let pending = false
    let controller: AbortController | undefined
    let timeout: number | undefined
    const timer = window.setInterval(() => {
      if (pending) return
      pending = true
      controller = new AbortController()
      timeout = window.setTimeout(() => controller?.abort(), 10_000)
      api.candidateProfile(controller.signal).then(data => {
      if (!active) return
      setProfile(data); setPollError('')
      if (data.latest_resume?.processing_status === 'completed') { setSettingsOpen(false); setMessage(data.resume_identity_warning ? '' : 'Your profile is ready.') }
    }).catch(() => { if (active) setPollError('Status unavailable') }).finally(() => { window.clearTimeout(timeout); pending = false }) }, 750)
    return () => { active = false; window.clearInterval(timer); window.clearTimeout(timeout); controller?.abort() }
  }, [processing, resumeId])
  async function refreshProcessing() {
    const controller = new AbortController()
    const timeout = window.setTimeout(() => controller.abort(), 10_000)
    try {
      const data = await api.candidateProfile(controller.signal)
      setProfile(data); setPollError('')
      if (data.latest_resume?.processing_status === 'completed') setSettingsOpen(false)
    } catch { setPollError('Status unavailable') }
    finally { window.clearTimeout(timeout) }
  }
  const save = (patch: Partial<Candidate>) => run(() => api.updateCandidate(patch))
  const prefs = (patch: CareerPreferences) => save({ career_preferences: patch })
  async function upload(file?: File) {
    if (!file) return
    if (!/\.(pdf|docx)$/i.test(file.name) || file.size > 5 * 1024 * 1024) { setError('Choose a PDF or DOCX, up to 5 MB.'); return }
    const accepted = await run(async () => { const data = await api.uploadResume(file); focusUpload.current = true; return data }, '')
    if (accepted) { setSettingsOpen(false); setReview(false); setSuccess(false); setEditing(false); setShowBeyond(false); setPollError('') }
  }
  async function uploadPhoto(file: File) {
    if (!/^image\/(jpeg|png|webp)$/i.test(file.type) || file.size > 4 * 1024 * 1024) {
      setError('Choose a JPG, PNG or WebP profile photo, up to 4 MB.'); return
    }
    await run(() => api.uploadCandidatePhoto(file), '')
  }
  if (!profile) return <main className="candidate-experience"><p role={error ? 'alert' : 'status'}>{error || 'Opening your profile…'}</p>{error && <button onClick={() => void run(api.candidateProfile, '')}>Try again</button>}</main>
  const p = profile, preferences = p.career_preferences || {}
  const skills = (preferences.strongest_skills ?? p.skills).slice(0, 5)
  const resume = p.available_resume ?? (p.latest_resume?.processing_status === 'completed' ? p.latest_resume : null)
  const title = professionalTitle(p)
  const college = collegeName(p.education)
  const identityDetails = [college, Number(p.total_experience) > 0 ? `${p.total_experience} years experience` : '', p.location].filter(Boolean)
  const professionalRead = enterRead(p, skills)
  const highlightTopics = skills.slice(0, 4)
  const settingsMissing = (p.submission_missing_fields || []).filter(item => ['notice_period_days', 'work_preferences'].includes(item.field))
  const profileMissing = p.submission_missing_fields || []
  const openSettings = (field?: string) => {
    setSettingsOpen(true)
    setEditingSettingsField(field || 'availability')
    setEditingSettings(true)
  }
  const uploadControl = <label className="cp-file"><span className="onboarding-choose">{busy ? 'Uploading…' : 'Choose file'}</span><input aria-label="Choose PDF or DOCX resume" data-testid="resume-input" type="file" accept=".pdf,.docx" disabled={busy || processing} onChange={e => { void upload(e.target.files?.[0]); e.target.value = '' }} /><small>PDF or DOCX · Maximum 5 MB</small></label>
  const replaceControl = <label className="cp-replace-control">Update<input aria-label="Update Resume" data-testid="resume-input" type="file" accept=".pdf,.docx" disabled={busy || processing} onChange={e => { void upload(e.target.files?.[0]); e.target.value = '' }} /></label>
  const processingView = p.latest_resume && (processing || status === 'failed') ? <CandidateProcessing key={p.latest_resume.id} resume={p.latest_resume} uploading={busy} retry={() => void run(() => api.retryResume(p.latest_resume!.id), '')} upload={file => void upload(file)} error={pollError} refresh={() => void refreshProcessing()} /> : null
  async function saveSettings(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const data = new FormData(event.currentTarget), get = (key: string) => String(data.get(key) || '').trim()
    const number = (key: string) => get(key) === '' ? null : get(key)
    let values: Partial<Candidate> = {}
    if (editingSettingsField === 'availability') values = { career_preferences: { availability: get('availability') } }
    if (editingSettingsField === 'notice_period_days') values = { notice_period_days: number('notice') === null ? null : Number(get('notice')) }
    if (editingSettingsField === 'current') values = { current_salary_lpa: number('current'), expected_salary_lpa: number('expected') }
    if (editingSettingsField === 'work_preferences') values = { work_preferences: get('setup') ? [get('setup')] : [], employment_type: get('employment'), career_preferences: { preferred_locations: list(get('locations')) } }
    if (editingSettingsField === 'email') values = { email: get('email'), phone: get('phone'), career_preferences: { contact_preferences: get('contact') ? [get('contact')] : [] } }
    if (editingSettingsField === 'linkedin') values = { linkedin_url: get('linkedin'), github_url: get('github') }
    const didSave = await save(values)
    if (didSave) setEditingSettings(false)
  }
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (busyRef.current) return
    if (!await flushAnswer()) return
    if (await run(() => api.submitCandidate(true), '')) { setSuccessAnimationComplete(false); setSuccess(true); setReview(false); setMeaningfulDraft(null) }
  }
  const settingsEditor = (field: string) => editingSettings && editingSettingsField === field ? <form key={`${p.profile_updated_at}:${editingSettingsField}`} onSubmit={saveSettings} className="cp-settings-editor cp-settings-inline-editor"><fieldset disabled={busy}><div className="cp-fields">
    {editingSettingsField === 'availability' && <label>Availability<select name="availability" defaultValue={preferences.availability || ''}><option value="">Not specified</option>{['Actively looking', 'Open to the right opportunity', 'Not looking right now'].map(value => <option key={value}>{value}</option>)}</select></label>}
    {editingSettingsField === 'notice_period_days' && <label>Notice period<select name="notice" defaultValue={p.notice_period_days ?? ''}><option value="">Select notice period</option>{p.notice_period_days !== null && !noticePeriods.includes(p.notice_period_days) && <option value={p.notice_period_days}>{p.notice_period_days} days</option>}{noticePeriods.map(value => <option key={value} value={value}>{value === 0 ? 'Immediately available' : `${value} days`}</option>)}</select></label>}
    {editingSettingsField === 'current' && <><label>Current CTC (₹ LPA)<input name="current" type="number" min={0} step="0.01" defaultValue={p.current_salary_lpa ?? ''} /></label><label>Expected CTC (₹ LPA)<input name="expected" type="number" min={0} step="0.01" defaultValue={p.expected_salary_lpa ?? ''} /></label></>}
    {editingSettingsField === 'work_preferences' && <><label>Preferred locations<input name="locations" defaultValue={(preferences.preferred_locations || []).join(', ')} placeholder="Separate locations with commas" /></label><label>Employment type<select name="employment" defaultValue={p.employment_type}><option value="">Select employment type</option>{p.employment_type && !employmentTypes.includes(p.employment_type) && <option value={p.employment_type}>{p.employment_type}</option>}{employmentTypes.map(value => <option key={value}>{value}</option>)}</select></label><label>Work setup<select name="setup" defaultValue={p.work_preferences[0] || ''}><option value="">Select work setup</option>{p.work_preferences[0] && !workSetups.includes(p.work_preferences[0]) && <option value={p.work_preferences[0]}>{p.work_preferences[0]}</option>}{workSetups.map(value => <option key={value}>{value}</option>)}</select></label></>}
    {editingSettingsField === 'email' && <><label>Email<input type="email" name="email" defaultValue={p.email} /></label><label>Phone<input type="tel" name="phone" defaultValue={p.phone} /></label><label>Contact preference<select name="contact" defaultValue={preferences.contact_preferences?.[0] || ''}><option value="">Select contact preference</option>{contactMethods.map(value => <option key={value}>{value}</option>)}</select></label></>}
    {editingSettingsField === 'linkedin' && <><label>LinkedIn<input type="url" name="linkedin" defaultValue={p.linkedin_url} /></label><label>GitHub / portfolio<input type="url" name="github" defaultValue={p.github_url} /></label></>}
  </div>
  <div className="cp-actions"><button className="primary">Update</button><button type="button" onClick={() => setEditingSettings(false)}>Cancel</button></div></fieldset></form> : null
  return <main className="candidate-experience" ref={mainRef}>
    <header className="cp-welcome"><h1>Let's find work that feels great.</h1><button type="button" className="cp-settings-toggle" aria-label="Career Settings" aria-expanded={settingsOpen} aria-controls="career-settings-panel" onClick={() => { if (success) setSuccessAnimationComplete(true); toggleSettings(success) }}><Settings aria-hidden="true" /><span>Career Settings</span></button></header>
    {error && <p role="alert" className="error">{error}</p>}<p aria-live="polite" aria-atomic="true" className="cp-sr-only">{message}</p>
    {success && !settingsOpen ? <section className={`cp-success ${successAnimationComplete ? 'cp-success-static' : ''}`}><div className="cp-success-copy"><h2>You're in.<svg className="cp-success-check" viewBox="0 0 36 36" aria-hidden="true"><circle cx="18" cy="18" r="15" /><path pathLength="1" d="m10.5 18 5 5 10-11" /></svg></h2><div className="cp-success-underline" aria-hidden="true" /><div className="cp-success-support" onAnimationEnd={event => { if (event.currentTarget === event.target) setSuccessAnimationComplete(true) }}><h3>We'll take it from here.</h3><p><EnterBrandText text="When ENTER finds something genuinely relevant, we'll reach out according to your preferences." /></p></div></div></section> : <>
    {processingView}
    <div className={`cp-profile-workspace ${settingsOpen ? 'settings-open' : ''}`}><div className="cp-profile-main">{(!p.latest_resume ? <section className="onboarding-upload"><div className="onboarding-upload-copy"><h2>Start with your resume.</h2><p>We'll do the reading. You tell us if we got it right.</p></div><div className={`cp-section cp-upload ${dragging ? 'dragging' : ''}`} onDragOver={e => { e.preventDefault(); setDragging(true) }} onDragLeave={e => { if (!e.currentTarget.contains(e.relatedTarget as Node | null)) setDragging(false) }} onDrop={e => { e.preventDefault(); setDragging(false); if (!busy) void upload(e.dataTransfer.files[0]) }}><FileText aria-hidden="true" className="onboarding-file-icon" /><h3>Drop your resume here</h3>{uploadControl}</div></section> : (processing || !resume) && processingView ? null : <>
      <section className="cp-section cp-profile" tabIndex={-1}><h2>Here's how we understand you.</h2>
        {p.resume_identity_warning && <div role="alert" className="cp-resume-updates"><strong>We couldn't match this resume to your profile.</strong><p>Your saved information is unchanged. Check the uploaded document and replace it with your own resume showing your correct name. We won't combine two people's career histories.</p><button onClick={() => setSettingsOpen(true)}>Choose the correct resume</button></div>}
        {editing ? <ProfileEditor profile={p} busy={busy} save={save} cancel={() => setEditing(false)} /> : <>
          <div className="cp-identity-card"><CandidatePhoto key={p.profile_photo_url || 'initials'} profile={p} busy={busy} upload={file => void uploadPhoto(file)} remove={() => void run(api.removeCandidatePhoto, '')} /><div className="cp-identity-column"><div className="cp-identity"><h3>{displayName(p.full_name)}</h3><p className="cp-professional-title">{title || 'Add your professional title'}</p>{identityDetails.length > 0 && <div className="cp-identity-meta">{college && <span><GraduationCap aria-hidden="true" />{college}</span>}{Number(p.total_experience) > 0 && <span><BriefcaseBusiness aria-hidden="true" />{p.total_experience} years experience</span>}{p.location && <span><MapPin aria-hidden="true" />{p.location}</span>}</div>}</div><div className="cp-professional-read"><h3>ENTER's read on you</h3><p>{professionalRead}</p></div></div><aside className="cp-highlight"><h3>What stood out to us</h3><p>{preferences.standout_signal || 'Add an evidence-backed achievement using “Not quite — edit”.'}</p>{preferences.standout_signal && highlightTopics.length > 0 && <div className="cp-highlight-topics">{highlightTopics.map(topic => <span key={topic}>{topic}</span>)}</div>}</aside></div>
          <div className="cp-career-surface"><CandidateCareerTimeline items={p.work_experiences} edit={() => setEditing(true)} />
          <div className="cp-skills"><h3>Strongest in</h3><p>Core skills and technologies from your saved profile.</p>{skills.length > 0 ? <div className="cp-skill-chips">{skills.map(skill => <span key={skill}>{skill}</span>)}</div> : <p>Choose the skills that best represent you.</p>}</div></div>
          {preferences.likely_directions?.length ? <div className="cp-likely"><h3>Likely direction</h3><p>{preferences.likely_directions.slice(0, 3).join(' · ')}</p></div> : null}
        </>}
        <div className="cp-resume-row"><CandidateResumePreview key={resume?.id} resume={resume} />
        {p.resume_review && <ResumeReview key={`${p.resume_review.resume_id}:${p.profile_updated_at}`} profile={p} busy={busy} apply={fields => void run(() => api.reviewResume(p.resume_review!.resume_id, fields, p.profile_updated_at, fields.length > 0), fields.length ? 'Profile updated.' : 'Profile kept unchanged.')} />}
        </div>
        {!editing && <><div className="cp-actions cp-profile-confirm"><button className="primary" disabled={busy} aria-expanded={showBeyond} aria-controls="beyond-cv" onClick={() => { const opening = !showBeyond; setShowBeyond(opening); if (opening) window.requestAnimationFrame(() => { document.getElementById('beyond-cv')?.focus(); document.getElementById('beyond-cv')?.scrollIntoView({ block: 'start' }) }) }}>That's me ✓</button><button onClick={() => void leave(() => setEditing(true))}>Not quite — edit</button></div>{profileMissing.length > 0 && <section className="cp-profile-required" role="status" aria-label="Required profile details"><strong>Complete your profile</strong><p>Add the required details before final confirmation.</p>{profileMissing.map(item => <button key={item.field} type="button" onClick={() => { if (item.field === 'visibility') { setReview(true); setSettingsOpen(false) } else if (['notice_period_days', 'work_preferences'].includes(item.field)) openSettings(item.field); else setEditing(true) }}>Add {item.label}</button>)}</section>}</>}
      </section>
      {!showBeyond && <div className="cp-beyond-next"><div><strong>Next: Beyond the CV</strong><p>Confirm your profile above to tell us what drives you.</p></div></div>}
      {showBeyond && <section className="cp-beyond" id="beyond-cv" tabIndex={-1}><h2>BEYOND THE CV</h2>
        <div className="cp-question cp-writing"><label>What is the most meaningful thing you've built?<textarea ref={answerInput} aria-label="What is the most meaningful thing you've built?" aria-describedby={answerError ? 'answer-save-error' : undefined} rows={1} maxLength={200} value={meaningfulDraft ?? p.meaningful_work} onChange={e => changeAnswer(e.target.value)} onBlur={() => void flushAnswer()} /></label>{answerError && <div id="answer-save-error" role="alert"><p>Your answer hasn't been saved. Your text is kept here; retry before leaving.</p><button type="button" onClick={() => void flushAnswer()}>Retry saving answer</button></div>}</div>
        <div className="cp-question"><h3>What would make you leave a job you actually like?</h3><div className="cp-choice-line"><Chips options={[...motivators, ...(preferences.custom_motivators || [])]} selected={preferences.motivators || []} disabled={busy} onChange={value => prefs({ motivators: value })} /><CustomChoice label="Your own motivation" disabled={busy} add={value => prefs({ custom_motivators: [...new Set([...(preferences.custom_motivators || []), value])], motivators: [...new Set([...(preferences.motivators || []), value])] })} /></div></div>
        <div className="cp-question"><h3>What should we NEVER call you for?</h3><div className="cp-choice-line"><Chips options={[...exclusions, ...(preferences.custom_exclusions || []), ...(preferences.exclusions || [])]} selected={preferences.exclusions || []} disabled={busy} onChange={value => prefs({ exclusions: value })} />
        <CustomChoice label="Your own exclusion" disabled={busy} add={value => prefs({ custom_exclusions: [...new Set([...(preferences.custom_exclusions || []), value])], exclusions: [...new Set([...(preferences.exclusions || []), value])] })} /></div>
        </div>
      </section>}
      {!editing && <div className="cp-final-confirm"><button type="button" className="primary" disabled={busy || processing} onClick={() => { setReview(true); setSettingsOpen(false) }}>Confirm my profile</button></div>}
    </>)}</div>
    {settingsOpen && <aside id="career-settings-panel" className="cp-settings-panel" aria-label="Career Settings panel"><section className="cp-section cp-settings"><header className="cp-settings-header"><div><h2>Career Settings</h2><p>Manage your preferences and how we reach you.</p></div></header>
    {settingsMissing.length > 0 && <div className="cp-settings-warning" role="status"><strong>Complete your career preferences</strong>{settingsMissing.map(item => <p key={item.field}>{item.message} <button type="button" onClick={() => openSettings(item.field)}>Add {item.label}</button></p>)}</div>}
    <div className="cp-settings-summary">
      <button type="button" className="cp-setting-row" onClick={() => openSettings('availability')}><span><Target aria-hidden="true" /></span><div><strong>Availability</strong><p>{preferences.availability || 'Not specified yet'}</p></div><span className="cp-setting-edit"><Pencil aria-hidden="true" />Edit</span></button>
      {settingsEditor('availability')}
      <div className="cp-setting-row"><span><BriefcaseBusiness aria-hidden="true" /></span><div><strong>Role &amp; direction</strong><p>{preferences.likely_directions?.join(' · ') || title || 'Not specified yet'}</p></div></div>
      <div className="cp-setting-row cp-spectrum-row"><span><UserRound aria-hidden="true" /></span><BuildLeadSpectrum value={p.build_lead_preference} save={value => save({ build_lead_preference: value })} /></div>
      <button type="button" className="cp-setting-row" onClick={() => openSettings('notice_period_days')}><span><Clock3 aria-hidden="true" /></span><div><strong>Notice period</strong><p>{p.notice_period_days === null ? 'Not specified yet' : `${p.notice_period_days} days`}</p></div><span className="cp-setting-edit"><Pencil aria-hidden="true" />Edit</span></button>
      {settingsEditor('notice_period_days')}
      <button type="button" className="cp-setting-row" onClick={() => openSettings('current')}><span><BadgeIndianRupee aria-hidden="true" /></span><div><strong>Compensation</strong><p>Current: {p.current_salary_lpa ? `₹${p.current_salary_lpa} LPA` : 'Not specified'} · Expected: {p.expected_salary_lpa ? `₹${p.expected_salary_lpa} LPA` : 'Not specified'}</p></div><span className="cp-setting-edit"><Pencil aria-hidden="true" />Edit</span></button>
      {settingsEditor('current')}
      <button type="button" className="cp-setting-row" onClick={() => openSettings('work_preferences')}><span><House aria-hidden="true" /></span><div><strong>Work preferences</strong><p>{[p.work_preferences.join(' / '), preferences.preferred_locations?.join(', '), p.employment_type].filter(Boolean).join(' · ') || 'Not specified yet'}</p></div><span className="cp-setting-edit"><Pencil aria-hidden="true" />Edit</span></button>
      {settingsEditor('work_preferences')}
      <button type="button" className="cp-setting-row" onClick={() => openSettings('email')}><span><Phone aria-hidden="true" /></span><div><strong>How should we reach you?</strong><p>{preferences.contact_preferences?.join(' / ') || p.email || p.phone || 'Not specified yet'}</p></div><span className="cp-setting-edit"><Pencil aria-hidden="true" />Edit</span></button>
      {settingsEditor('email')}
      <button type="button" className="cp-setting-row" onClick={() => openSettings('linkedin')}><span><Link2 aria-hidden="true" /></span><div><strong>Professional links</strong><p>{[p.linkedin_url, p.github_url].filter(Boolean).join(' · ') || 'Not specified yet'}</p></div><span className="cp-setting-edit"><Pencil aria-hidden="true" />Edit</span></button>
      {settingsEditor('linkedin')}
      <div className="cp-setting-row cp-setting-resume"><span><FileText aria-hidden="true" /></span><div><strong>Resume</strong><p>{resume?.original_name || 'No completed resume'}</p></div>{replaceControl}</div>
    </div>
    </section></aside>}</div>
    {review && <section className="cp-section cp-brief"><h2>Here's how we'll remember you</h2><h3>{p.full_name}</h3><p>{title}{p.location && ` · ${p.location}`}</p><p>{skills.join(' · ')}</p>{preferences.standout_signal && <p>{preferences.standout_signal}</p>}<p>{preferences.availability || 'Availability not specified'} · {p.work_preferences.join(' / ') || 'Work setup to confirm'}</p>{preferences.motivators?.length ? <p>Drawn to {preferences.motivators.join(', ')}</p> : null}{preferences.exclusions?.length ? <p>Not interested in {preferences.exclusions.join(', ')}</p> : null}
      {p.submission_missing_fields.length > 0 && <div role="status"><p>Before confirming, complete:</p><ul>{p.submission_missing_fields.map(field => <li key={field.field}>{field.label}</li>)}</ul><div className="cp-actions">{p.submission_missing_fields.map(field => <button key={field.field} type="button" onClick={() => {
        if (field.field === 'visibility') {
          document.getElementById('profile-visibility-select')?.focus({ preventScroll: true })
          return
        }
        if (['notice_period_days', 'work_preferences'].includes(field.field)) {
          setReview(false)
          openSettings(field.field)
          return
        }
        setReview(false)
        setEditing(true)
      }}>{field.field === 'visibility' ? 'Choose profile visibility below' : `Add ${field.label}`}</button>)}</div></div>}
      {!p.visibility && <label>Who may discover your profile?<select id="profile-visibility-select" aria-label="First-time profile visibility" value="" disabled={busy} onChange={e => { if (e.target.value) void save({ visibility: e.target.value as Candidate['visibility'] }) }}><option value="">Choose before giving consent</option><option value="approved_recruiters">Approved ENTER recruiters</option><option value="matching_roles">Only matching roles</option><option value="not_looking">Not looking right now — hidden</option></select></label>}
      <form onSubmit={submit}><label className="cp-check"><input type="checkbox" required />I agree to share my profile with authorized ENTER recruiters according to my visibility preferences.</label><div className="cp-actions"><a href="/privacy" target="_blank" rel="noopener noreferrer">Privacy Policy</a><a href="/terms" target="_blank" rel="noopener noreferrer">Terms</a><button className="primary" disabled={busy || !p.can_submit || processing}>Yes, that's me ✓</button><button type="button" onClick={() => setReview(false)}>Keep editing</button></div></form>
    </section>}
    </>}
    {!success && <footer className="cp-footer" aria-label="Candidate help links"><div className="cp-footer-row"><img src="/enter-wordmark.svg" alt="ENTER" /><div className="cp-footer-links"><button aria-expanded={footerPanel === 'support'} onClick={() => void leave(() => setFooterPanel(value => value === 'support' ? null : 'support'))}>Help Center</button></div><div className="cp-connect"><strong>Connect with us</strong><div><a className="cp-footer-icon" href="https://www.linkedin.com/company/enterrecruitment/posts/?feedView=all" target="_blank" rel="noopener noreferrer" aria-label="ENTER Recruitment on LinkedIn"><LinkedInIcon /></a><a className="cp-footer-icon" href="https://www.enterrecruitment.com/" target="_blank" rel="noopener noreferrer" aria-label="ENTER Recruitment website"><Globe2 aria-hidden="true" /></a></div></div></div>{footerPanel === 'support' && <section className="cp-footer-panel"><h2>Help Center</h2><p>For help with your profile, contact your ENTER representative.</p><div className="cp-faqs"><h3>Frequently asked questions</h3><details><summary>How do I update my Career Journey?</summary><p>Use “Not quite — edit” to correct saved profile details, or review Resume updates after replacing a resume.</p></details><details><summary>When will my resume be ready?</summary><p>ENTER shows the processing state while your uploaded document is being read. Your profile opens automatically when processing is complete.</p></details><details><summary>How do I change what opportunities I receive?</summary><p>Open Career Settings to update availability, notice period, compensation, work setup, locations, and contact preferences.</p></details><details><summary>Can I delete my profile?</summary><p>Open your name in the top-right account menu to access account deletion.</p></details></div></section>}</footer>}
  </main>
}
