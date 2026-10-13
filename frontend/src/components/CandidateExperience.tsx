import { useEffect, useRef, useState } from 'react'
import type { FormEvent } from 'react'
import { api } from '../api'
import type { Candidate, CareerPreferences, WorkExperience } from '../types'
import { CandidateProcessing } from './CandidatePresentation'
import CandidateCareerTimeline from './CandidateCareerTimeline'
import CandidateResumePreview from './CandidateResumePreview'
import { likelyDirections, professionalTitle } from '../candidateIdentity'
import './candidate-experience.css'

const motivators = ['Exceptional team', 'Harder problems', 'More ownership', 'Compensation', 'Founding team', 'Leadership', 'Product', 'Global exposure', 'Founder']
const exclusions = ['5-day WFO', 'Services companies', 'Pure management', 'Java roles', 'Below ₹50L', 'Large companies']
const list = (text: string) => [...new Set(text.split(/[,\n]/).map(value => value.trim()).filter(Boolean))]
const label = (key: string) => key.replaceAll('_', ' ')

function Chips({ options, selected, onChange, disabled = false }: { options: string[]; selected: string[]; onChange: (value: string[]) => void; disabled?: boolean }) {
  return <div className="cp-chips">{[...new Set(options)].map(option => <button type="button" key={option} disabled={disabled} aria-pressed={selected.includes(option)} onClick={() => onChange(selected.includes(option) ? selected.filter(value => value !== option) : [...selected, option])}>{option}</button>)}</div>
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
      career_preferences: { strongest_skills: list(get('strongest_skills')), standout_signal: get('standout_signal'), likely_directions: list(get('likely_directions')) },
    }
    if (await save(patch)) cancel()
  }
  return <form className="cp-editor" onSubmit={submit}>
    <h3>Let's get it right.</h3><fieldset disabled={busy}><div className="cp-fields">
      {(['full_name', 'headline', 'current_company', 'location', 'total_experience'] as const).map(key => <label key={key}>{label(key)}<input name={key} defaultValue={key === 'headline' ? professionalTitle(profile) : profile[key]} type={key === 'total_experience' ? 'number' : 'text'} min={0} step="0.1" required={key === 'full_name'} /></label>)}
      <label>All skills<input name="skills" defaultValue={profile.skills.join(', ')} /></label>
      <label>Strongest skills (up to five)<input name="strongest_skills" defaultValue={(profile.career_preferences?.strongest_skills ?? profile.skills.slice(0, 5)).join(', ')} /></label>
      <label>Standout signal<input name="standout_signal" maxLength={1000} defaultValue={profile.career_preferences?.standout_signal || ''} /></label>
      <label>Likely direction<input name="likely_directions" defaultValue={likelyDirections(profile).join(', ')} placeholder="Add or correct a possible direction" /></label>
      <label>About<textarea name="summary" defaultValue={profile.summary} /></label>
      <label>Education (one entry per line)<textarea name="education" defaultValue={profile.education.join('\n')} /></label>
    </div>
    <h3>Career history</h3><p className="cp-muted">Leave unknown dates empty. Mark a role current only if it is ongoing.</p>
    {rows.map((row, i) => <div className="cp-work-edit" key={i}>
      <label>Company {i + 1}<input required value={row.company} onChange={e => update(i, { company: e.target.value })} /></label>
      <label>Job title {i + 1}<input required value={row.role} onChange={e => update(i, { role: e.target.value })} /></label>
      <label>Start date {i + 1}<input type="date" value={row.start_date || ''} onChange={e => update(i, { start_date: e.target.value || null, date_label: /present|current|now/i.test(row.date_label || '') ? `${e.target.value || 'Start not specified'} — Present` : '' })} /></label>
      <label>End date {i + 1}<input type="date" value={row.end_date || ''} onChange={e => update(i, { end_date: e.target.value || null, date_label: '' })} /></label>
      <label className="cp-check"><input type="checkbox" checked={/present|current|now/i.test(row.date_label || '') && !row.end_date} onChange={e => update(i, { end_date: e.target.checked ? null : row.end_date, date_label: e.target.checked ? `${row.start_date || 'Start not specified'} — Present` : '' })} />Current role</label>
      <label>Career gap context {i + 1}<input value={row.gap_reason} onChange={e => update(i, { gap_reason: e.target.value })} /></label>
      <details><summary>Edit saved role details</summary><label>Role details {i + 1}<textarea value={row.description} onChange={e => update(i, { description: e.target.value })} /></label></details>
      <button type="button" onClick={() => setRows(rows.filter((_, index) => index !== i))}>Remove role {i + 1}</button>
    </div>)}
    <button type="button" onClick={() => setRows([...rows, { company: '', role: '', start_date: null, end_date: null, description: '', gap_reason: '', date_label: '' }])}>Add experience</button>
    <div className="cp-actions"><button className="primary" type="submit">Save corrections</button><button type="button" onClick={cancel}>Cancel</button></div>
    </fieldset></form>
}

function ResumeReview({ profile, apply, busy }: { profile: Candidate; apply: (fields: string[]) => void; busy: boolean }) {
  const [selected, setSelected] = useState<string[]>([])
  if (!profile.resume_review) return null
  const display = (value: unknown) => Array.isArray(value) ? value.map(item => typeof item === 'object' ? `${item.company} · ${item.role} · ${item.start_date || 'Unknown start'} — ${item.end_date || item.date_label || 'Unknown end'}` : String(item)).join('\n') : String(value ?? 'Not specified')
  return <details className="cp-resume-updates"><summary>Resume updates ({Object.keys(profile.resume_review.fields).length})</summary><p className="cp-muted">{profile.resume_review.original_name || 'Your resume'} has updates that need your choice. Your saved corrections are protected. You can review these later.</p>
    {Object.entries(profile.resume_review.fields).map(([key, value]) => <details key={key} className="cp-review-field"><summary>{label(key)}</summary><div className="cp-fields"><div><small>Saved</small><p>{display(profile[key as keyof Candidate])}</p></div><div><small>New resume</small><p>{display(value)}</p></div></div><label className="cp-check"><input type="checkbox" checked={selected.includes(key)} disabled={busy} onChange={e => setSelected(e.target.checked ? [...selected, key] : selected.filter(item => item !== key))} />Replace {label(key)}</label></details>)}
    <div className="cp-actions"><button className="primary" disabled={busy || !selected.length} onClick={() => apply(selected)}>Apply selected changes</button><button disabled={busy} onClick={() => apply([])}>Keep my saved profile</button></div>
  </details>
}

export default function CandidateExperience({ accountDeleted }: { accountDeleted: () => void }) {
  const [profile, setProfile] = useState<Candidate | null>(null)
  const [tab, setTab] = useState('My Profile')
  const [error, setError] = useState('')
  const [message, setMessage] = useState('')
  const [busy, setBusy] = useState(false)
  const busyRef = useRef(false)
  const [editing, setEditing] = useState(false)
  const [review, setReview] = useState(false)
  const [success, setSuccess] = useState(false)
  const [adding, setAdding] = useState(false)
  const [custom, setCustom] = useState('')
  const [deleting, setDeleting] = useState(false)
  const [dragging, setDragging] = useState(false)
  const [pollError, setPollError] = useState('')
  const mainRef = useRef<HTMLElement>(null)
  const wasProcessing = useRef(false)
  const focusUpload = useRef(false)
  const [meaningfulDraft, setMeaningfulDraft] = useState<string | null>(null)
  async function run(action: () => Promise<Candidate>, notice = 'Saved.') {
    if (busyRef.current) return false
    busyRef.current = true; setBusy(true); setError(''); setMessage('')
    try { setProfile(await action()); setMessage(notice); return true }
    catch (cause) { setError(cause instanceof Error ? cause.message : 'Could not save. Please try again.'); return false }
    finally { busyRef.current = false; setBusy(false) }
  }
  useEffect(() => { let active = true; api.candidateProfile().then(data => { if (active) setProfile(data) }).catch(cause => { if (active) setError(cause.message) }); return () => { active = false } }, [])
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
      if (data.latest_resume?.processing_status === 'completed') { setTab('My Profile'); setMessage('Your profile is ready.') }
    }).catch(() => { if (active) setPollError('Status unavailable') }).finally(() => { window.clearTimeout(timeout); pending = false }) }, 750)
    return () => { active = false; window.clearInterval(timer); window.clearTimeout(timeout); controller?.abort() }
  }, [processing, resumeId])
  async function refreshProcessing() {
    const controller = new AbortController()
    const timeout = window.setTimeout(() => controller.abort(), 10_000)
    try {
      const data = await api.candidateProfile(controller.signal)
      setProfile(data); setPollError('')
      if (data.latest_resume?.processing_status === 'completed') setTab('My Profile')
    } catch { setPollError('Status unavailable') }
    finally { window.clearTimeout(timeout) }
  }
  const save = (patch: Partial<Candidate>) => run(() => api.updateCandidate(patch))
  const prefs = (patch: CareerPreferences) => save({ career_preferences: patch })
  async function upload(file?: File) {
    if (!file) return
    if (!/\.(pdf|docx)$/i.test(file.name) || file.size > 5 * 1024 * 1024) { setError('Choose a PDF or DOCX, up to 5 MB.'); return }
    const accepted = await run(async () => { const data = await api.uploadResume(file); focusUpload.current = true; return data }, '')
    if (accepted) { setTab('My Profile'); setReview(false); setSuccess(false); setEditing(false); setPollError('') }
  }
  if (!profile) return <main className="candidate-experience"><p role={error ? 'alert' : 'status'}>{error || 'Opening your profile…'}</p>{error && <button onClick={() => void run(api.candidateProfile, '')}>Try again</button>}</main>
  const p = profile, preferences = p.career_preferences || {}
  const skills = (preferences.strongest_skills ?? p.skills).slice(0, 5)
  const resume = p.available_resume ?? (p.latest_resume?.processing_status === 'completed' ? p.latest_resume : null)
  const directions = likelyDirections(p)
  const title = professionalTitle(p)
  const uploadControl = <label className="cp-file">Choose PDF or DOCX resume<input aria-label="Choose PDF or DOCX resume" data-testid="resume-input" type="file" accept=".pdf,.docx" disabled={busy || processing} onChange={e => { void upload(e.target.files?.[0]); e.target.value = '' }} /><small>PDF or DOCX · Maximum 5 MB</small></label>
  const processingView = p.latest_resume && (processing || status === 'failed') ? <CandidateProcessing key={p.latest_resume.id} resume={p.latest_resume} uploading={busy} retry={() => void run(() => api.retryResume(p.latest_resume!.id), '')} upload={file => void upload(file)} error={pollError} refresh={() => void refreshProcessing()} /> : null
  async function saveSettings(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const confirm = (event.nativeEvent as SubmitEvent).submitter?.getAttribute('value') === 'confirm'
    const data = new FormData(event.currentTarget), get = (key: string) => String(data.get(key) || '').trim()
    const number = (key: string) => get(key) === '' ? null : get(key)
    const didSave = await save({ notice_period_days: number('notice') === null ? null : Number(get('notice')), current_salary_lpa: number('current'), expected_salary_lpa: number('expected'),
      work_preferences: data.getAll('setup').map(String),
      email: get('email'), phone: get('phone'), linkedin_url: get('linkedin'), github_url: get('github'), employment_type: get('employment'),
      career_preferences: { availability: get('availability'), preferred_locations: list(get('locations')), contact_preferences: data.getAll('contact').map(String) },
    })
    if (didSave && confirm) setReview(true)
  }
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (busyRef.current) return
    if (meaningfulDraft !== null && !await save({ meaningful_work: meaningfulDraft })) return
    if (await run(() => api.submitCandidate(true), '')) { setSuccess(true); setReview(false); setMeaningfulDraft(null) }
  }
  return <main className="candidate-experience" ref={mainRef}>
    <header className="cp-welcome"><h1>Let's find work. That feels great.</h1></header>
    <nav className="cp-navigation" aria-label="Candidate sections">{['My Profile', 'Career Settings', 'Help'].map(name => <button key={name} aria-current={tab === name ? 'page' : undefined} onClick={() => { setTab(name); setReview(false); setSuccess(false) }}>{name}</button>)}</nav>
    {error && <p role="alert" className="error">{error}</p>}{message && <p role="status" className="cp-saved">{message}</p>}
    {success ? <section className="cp-success"><h2>You're in.</h2><h3>We'll take it from here.</h3><p>When ENTER finds something genuinely relevant, we'll reach out according to your preferences.</p></section> : <>
    {processingView}
    {tab === 'My Profile' && (!p.latest_resume ? <section className={`cp-section cp-upload ${dragging ? 'dragging' : ''}`} onDragOver={e => { e.preventDefault(); setDragging(true) }} onDragLeave={() => setDragging(false)} onDrop={e => { e.preventDefault(); setDragging(false); void upload(e.dataTransfer.files[0]) }}><h2>Drop your resume</h2>{uploadControl}</section> : (processing || !resume) && processingView ? null : <>
      <section className="cp-section" tabIndex={-1}><h2>My Profile</h2><p className="cp-muted">Here's how we understand you.</p>
        {editing ? <ProfileEditor profile={p} busy={busy} save={save} cancel={() => setEditing(false)} /> : <>
          <div className="cp-identity"><h3>{p.full_name}</h3><p>{title || 'Add your professional title'}</p><p className="cp-muted">{Number(p.total_experience) > 0 ? `${p.total_experience} years` : 'Experience to confirm'}{p.location && ` · ${p.location}`}</p></div>
          <CandidateCareerTimeline items={p.work_experiences} />
          <div className="cp-signals"><div><h3>Strongest In</h3><p>{skills.join(' · ') || 'Choose the skills that best represent you.'}</p></div><div><h3>Standout signal</h3><p>{preferences.standout_signal || 'No clear achievement identified. Add one using “Not quite — edit”.'}</p></div><div><h3>Likely direction</h3><p>{directions.join(' · ') || 'Add a possible direction using “Not quite — edit”.'}</p>{directions.length > 0 && <small className="cp-muted">A possible direction, not a confirmed job preference.</small>}</div></div>
          <div className="cp-actions"><button className="primary" disabled={busy} onClick={() => { document.getElementById('beyond-cv')?.focus(); document.getElementById('beyond-cv')?.scrollIntoView({ block: 'start' }) }}>That's me ✓</button><button onClick={() => setEditing(true)}>Not quite — edit</button></div>
        </>}
        <CandidateResumePreview key={resume?.id} resume={resume} />
        {p.resume_review && <ResumeReview key={`${p.resume_review.resume_id}:${p.profile_updated_at}`} profile={p} busy={busy} apply={fields => void run(() => api.reviewResume(p.resume_review!.resume_id, fields, p.profile_updated_at, fields.length > 0), 'Resume updates saved.')} />}
      </section>
      <section className="cp-section" id="beyond-cv" tabIndex={-1}><h2>BEYOND THE CV</h2>
        <form onSubmit={async e => { e.preventDefault(); if (await save({ meaningful_work: meaningfulDraft ?? p.meaningful_work })) setMeaningfulDraft(null) }}><label>What is the most meaningful thing you've built?<textarea aria-label="What is the most meaningful thing you've built?" rows={3} value={meaningfulDraft ?? p.meaningful_work} onChange={e => setMeaningfulDraft(e.target.value)} /></label><button disabled={busy}>Save answer</button></form>
        <h3>What would make you leave a job you actually like?</h3><Chips options={motivators} selected={preferences.motivators || []} disabled={busy} onChange={value => void prefs({ motivators: value })} />
        <h3>What should we NEVER call you for?</h3><Chips options={[...exclusions, ...(preferences.custom_exclusions || []), ...(preferences.exclusions || [])]} selected={preferences.exclusions || []} disabled={busy} onChange={value => void prefs({ exclusions: value })} />
        {adding ? <form className="cp-actions cp-custom-exclusion" onSubmit={async e => { e.preventDefault(); if (custom.trim() && await prefs({ custom_exclusions: [...new Set([...(preferences.custom_exclusions || []), custom.trim()])], exclusions: [...new Set([...(preferences.exclusions || []), custom.trim()])] })) { setCustom(''); setAdding(false) } }}><label>Your own exclusion<input autoFocus maxLength={240} value={custom} onChange={e => setCustom(e.target.value)} required /></label><button disabled={busy}>Add option</button><button type="button" onClick={() => setAdding(false)}>Cancel</button></form> : <button onClick={() => setAdding(true)}>+ Add my own</button>}
      </section>
      <button className="primary" disabled={busy || editing} onClick={() => setTab('Career Settings')}>Continue to Career Settings</button>
    </>)}
    {tab === 'Career Settings' && <section className="cp-section"><h2>Career Settings</h2><form key={p.profile_updated_at} onSubmit={saveSettings}><fieldset disabled={busy}><div className="cp-fields">
      <label>Availability<select name="availability" defaultValue={preferences.availability || ''}><option value="">Not specified</option>{['Actively looking', 'Open to the right opportunity', 'Not looking right now'].map(value => <option key={value}>{value}</option>)}</select></label>
      <label>Notice Period (days)<input name="notice" type="number" min={0} defaultValue={p.notice_period_days ?? ''} /></label>
      <label>Current CTC (₹ LPA)<input name="current" type="number" min={0} step="0.01" defaultValue={p.current_salary_lpa ?? ''} /></label>
      <label>Expected CTC (₹ LPA)<input name="expected" type="number" min={0} step="0.01" defaultValue={p.expected_salary_lpa ?? ''} /></label>
      <label>Preferred locations<input name="locations" defaultValue={(preferences.preferred_locations || []).join(', ')} placeholder="Separate locations with commas" /></label>
      <label>Employment type<input name="employment" defaultValue={p.employment_type} /></label>
      <label>Email<input type="email" name="email" defaultValue={p.email} /></label><label>Phone<input type="tel" name="phone" defaultValue={p.phone} /></label>
      <label>LinkedIn<input type="url" name="linkedin" defaultValue={p.linkedin_url} /></label><label>GitHub / portfolio<input type="url" name="github" defaultValue={p.github_url} /></label>

    </div><fieldset><legend>Work Setup</legend><div className="cp-chips">{['Remote', 'Hybrid', 'On-site', 'Flexible'].map(value => <label className="cp-choice" key={value}><input type="checkbox" name="setup" value={value} defaultChecked={p.work_preferences.includes(value)} />{value}</label>)}</div></fieldset>
    <fieldset><legend>Contact Preference</legend><div className="cp-chips">{['Email', 'WhatsApp', 'Phone'].map(value => <label className="cp-choice" key={value}><input type="checkbox" name="contact" value={value} defaultChecked={preferences.contact_preferences?.includes(value)} />{value}</label>)}</div></fieldset>
    <div className="cp-actions"><button className="primary">Save Career Settings</button><button type="submit" value="confirm" disabled={busy || processing}>Confirm my profile</button></div></fieldset></form>
    <div className="cp-replace"><h3>Replace Resume</h3><p className="cp-muted">Safe resume updates apply automatically. Your saved corrections and Beyond the CV answers stay protected.</p>{uploadControl}</div>
    </section>}
    {tab === 'Help' && <section className="cp-section cp-help"><h2>Help</h2><h3>Support</h3><p>For help with your profile, contact your ENTER representative.</p><h3>Privacy</h3><p>Your saved privacy settings and consent control recruiter access to your profile.</p><div className="cp-actions"><a href="/privacy" target="_blank" rel="noopener noreferrer">Privacy Policy</a><a href="/terms" target="_blank" rel="noopener noreferrer">Terms</a></div><h3>Account</h3><p>Deleting your account permanently removes your profile and uploaded resumes.</p>{!deleting ? <button className="cp-danger" onClick={() => setDeleting(true)}>Delete my account</button> : <form onSubmit={async e => { e.preventDefault(); if (busyRef.current) return; const data = new FormData(e.currentTarget); busyRef.current = true; setBusy(true); try { await api.deleteCandidateAccount(String(data.get('password')), String(data.get('confirmation'))); accountDeleted() } catch (cause) { setError(cause instanceof Error ? cause.message : 'Could not delete account.') } finally { busyRef.current = false; setBusy(false) } }}><label>Current password<input type="password" name="password" autoComplete="current-password" required /></label><label>Type DELETE to confirm<input name="confirmation" required pattern="DELETE" /></label><div className="cp-actions"><button disabled={busy} className="cp-danger">Permanently delete my account</button><button type="button" onClick={() => setDeleting(false)}>Cancel</button></div></form>}</section>}
    {review && <section className="cp-section cp-brief"><h2>Here's how we'll remember you</h2><h3>{p.full_name}</h3><p>{title}{p.location && ` · ${p.location}`}</p><p>{skills.join(' · ')}</p>{preferences.standout_signal && <p>{preferences.standout_signal}</p>}<p>{preferences.availability || 'Availability not specified'} · {p.work_preferences.join(' / ') || 'Work setup to confirm'}</p>{preferences.motivators?.length ? <p>Drawn to {preferences.motivators.join(', ')}</p> : null}{preferences.exclusions?.length ? <p>Not interested in {preferences.exclusions.join(', ')}</p> : null}
      {p.submission_missing_fields.length > 0 && <div role="status"><p>Before confirming, complete:</p><ul>{p.submission_missing_fields.map(field => <li key={field.field}>{field.label}</li>)}</ul><button onClick={() => { setTab('My Profile'); setEditing(true); setReview(false) }}>Edit My Profile</button></div>}
      {!p.visibility && <label>Who may discover your profile?<select aria-label="First-time profile visibility" value="" disabled={busy} onChange={e => { if (e.target.value) void save({ visibility: e.target.value as Candidate['visibility'] }) }}><option value="">Choose before giving consent</option><option value="approved_recruiters">Approved ENTER recruiters</option><option value="matching_roles">Only matching roles</option><option value="not_looking">Not looking right now — hidden</option></select></label>}
      <form onSubmit={submit}><label className="cp-check"><input type="checkbox" required />I agree to share my profile with authorized ENTER recruiters according to my visibility preferences.</label><div className="cp-actions"><a href="/privacy" target="_blank" rel="noopener noreferrer">Privacy Policy</a><a href="/terms" target="_blank" rel="noopener noreferrer">Terms</a><button className="primary" disabled={busy || !p.can_submit || processing}>Yes, that's me ✓</button><button type="button" onClick={() => setReview(false)}>Keep editing</button></div></form>
    </section>}
    </>}
  </main>
}
