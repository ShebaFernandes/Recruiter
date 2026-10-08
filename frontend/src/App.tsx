import { FormEvent, useEffect, useMemo, useRef, useState } from 'react'
import {
  ArrowRight, Bell, BriefcaseBusiness, CalendarDays, Check,
  Download, CheckCircle2, Code2, Eye, EyeOff, FileText, FolderPlus, GraduationCap,
  History, IndianRupee, Link, LogOut, Mail, MapPin, MessageCircle, Pencil, Plus,
  Search as SearchIcon, ShieldCheck, SlidersHorizontal, Sparkles, Target, Trash2,
  UploadCloud, X, Zap,
} from 'lucide-react'
import { api, ApiError, auth } from './api'
import type { AuthPayload } from './api'
import type { Candidate, Notification, Project, ProjectDetail, Search, SearchResult, User, WorkExperience } from './types'
import { Badge, Button, Card, FormField } from './components/ui'
import Landing from './components/Landing'
import RecruiterSearch from './components/RecruiterSearch'
import ResumeAccess from './components/ResumeAccess'
import { GithubMark, LinkedInMark } from './components/ProfileMarks'
import { ProjectWorkspace, WorkspacePanel } from './components/RecruiterWorkspace'
import { CandidateProcessing, CandidateWelcome } from './components/CandidatePresentation'
import './components/auth.css'

type SpeechRecognitionLike = {
  lang: string
  interimResults: boolean
  start: () => void
  onresult: ((event: { results: { 0: { 0: { transcript: string } } } }) => void) | null
  onerror: (() => void) | null
  onend: (() => void) | null
}
type SpeechRecognitionConstructor = new () => SpeechRecognitionLike

const emptyProfile: Candidate = {
  id: 0, full_name: '', headline: '', current_company: '', email: '', phone: '', location: '',
  total_experience: '0', notice_period_days: null, current_salary_lpa: null,
  expected_salary_lpa: null, employment_type: 'Full-time', linkedin_url: '', github_url: '',
  summary: '', meaningful_work: '', visibility: '', work_preferences: [],
  skills: [], education: [], profile_status: 'draft', email_verified_at: null, submitted_at: null,
  submission_consent_at: null, submission_consent_version: '', discovery_status: 'draft',
  profile_updated_at: '', work_experiences: [], latest_resume: null,
  viewed: false, stage: '', resume_updated: false, update_label: '', missing_fields: [],
  profile_completion: { percent: 0, remaining: 0, required_missing: 0, recommended_missing: 0 },
  submission_missing_fields: [], can_submit: false,
}

const recruiterStages = [
  ['sourced', 'Sourced'],
  ['shortlisted', 'Shortlisted'],
  ['contacted', 'Contacted'],
  ['screening', 'Screening'],
  ['interviewing', 'Interviewing'],
  ['offered', 'Offered'],
  ['rejected', 'Rejected'],
  ['non_relevant', 'Not relevant'],
  ['hired', 'Hired'],
] as const

const nonRelevantOptions = [
  'Wrong depth',
  'Wrong company context',
  'Skill not deep enough',
  'Wrong seniority',
  'Wrong location',
  'Not enough evidence',
] as const

function recruiterStageLabel(value: string) {
  return recruiterStages.find(([key]) => key === value)?.[1] || 'Recruiting stage'
}

function Brand({ compact = false }: { compact?: boolean }) {
  return <div className={`brand ${compact ? 'brand-compact' : ''}`}>
    <img src="/enter-logo.jpeg" alt="enter" />
    <span>Talent Platform</span>
  </div>
}

function InlineError({ value }: { value: string }) {
  return value ? <div className="error" role="alert">{value}</div> : null
}

function useDialogFocus(onClose: () => void) {
  const dialogRef = useRef<HTMLElement | null>(null)
  const closeRef = useRef(onClose)
  useEffect(() => {
    closeRef.current = onClose
  }, [onClose])
  useEffect(() => {
    const dialog = dialogRef.current
    const previous = document.activeElement as HTMLElement | null
    const oldOverflow = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    const focusable = () => Array.from(dialog?.querySelectorAll<HTMLElement>('button:not(:disabled), a[href], input:not(:disabled), select:not(:disabled), textarea:not(:disabled), [tabindex]:not([tabindex="-1"])') || [])
    ;(focusable()[0] || dialog)?.focus()
    const handleKey = (event: KeyboardEvent) => {
      if (event.key === 'Escape') { event.preventDefault(); closeRef.current(); return }
      if (event.key !== 'Tab') return
      const items = focusable()
      if (!items.length) { event.preventDefault(); dialog?.focus(); return }
      const first = items[0]
      const last = items[items.length - 1]
      if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last.focus() }
      else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus() }
    }
    document.addEventListener('keydown', handleKey)
    return () => {
      document.removeEventListener('keydown', handleKey)
      document.body.style.overflow = oldOverflow
      previous?.focus()
    }
  }, [])
  return dialogRef
}


function AuthLayout({ role, back, children }: {
  role?: 'candidate' | 'recruiter'
  back?: () => void
  children: React.ReactNode
}) {
  const candidate = role === 'candidate'
  return <main className="auth-page auth-editorial">
    <header className="auth-masthead">
      <Brand />
      {back ? <Button variant="ghost" size="small" onClick={back}>← Back to Enter</Button> : <a href="/">← Back to Enter</a>}
    </header>
    <div className="auth-layout">
      <aside className="auth-story">
        <div className="auth-story__copy">
          <span className="auth-context-label">{role ? candidate ? 'FOR CANDIDATES' : 'FOR RECRUITERS' : 'YOUR ENTER ACCOUNT'}</span>
          <h2>{role ? candidate ? 'Your work. Your story.' : 'Good hiring starts with understanding.' : 'A simple way back to what’s next.'}</h2>
          <p>{!role ? 'Manage access to your Enter account and pick up where you left off.' : candidate
            ? 'Turn your resume into a profile you control, then decide how the right recruiters can find you.'
            : 'Describe the work, clarify what matters, and build a shortlist from real candidate evidence.'}</p>
        </div>
      </aside>
      <section className="auth-content">{children}</section>
    </div>
  </main>
}

function AuthScreen({ role, onDone, back, initialMode = 'signup' }: {
  role: 'candidate' | 'recruiter'; onDone: (payload: AuthPayload) => void; back: () => void
  initialMode?: 'signup' | 'login'
}) {
  const [mode, setMode] = useState<'signup' | 'login' | 'forgot'>(initialMode)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [message, setMessage] = useState('')
  const [pendingEmail, setPendingEmail] = useState('')
  const [localVerificationUrl, setLocalVerificationUrl] = useState('')
  useEffect(() => {
    document.documentElement.scrollTop = 0
    document.body.scrollTop = 0
  }, [])
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); setBusy(true); setError(''); setMessage('')
    const data = Object.fromEntries(new FormData(event.currentTarget).entries()) as Record<string, string>
    try {
      if (mode === 'forgot') {
        const response = await api.requestPasswordReset(data.email)
        setMessage(response.detail)
        return
      }
      const payload = mode === 'signup'
        ? await api.signup({ ...data, role })
        : await api.login({ email: data.email, password: data.password })
      if ('requires_email_verification' in payload) {
        setPendingEmail(data.email)
        setLocalVerificationUrl(payload.local_verification_url || '')
        setMessage(payload.detail)
        return
      }
      if (payload.user.role !== role) throw new ApiError(`This account belongs to the ${payload.user.role} platform.`, 400)
      auth.save(payload); onDone(payload)
    } catch (err) {
      if (role === 'candidate' && mode === 'login' && err instanceof ApiError && err.status === 403) {
        setPendingEmail(data.email)
      }
      setError(err instanceof Error ? err.message : 'Could not continue.')
    }
    finally { setBusy(false) }
  }
  async function resend() {
    setBusy(true); setError('')
    try { setMessage((await api.resendVerification(pendingEmail)).detail) }
    catch (err) { setError(err instanceof Error ? err.message : 'Could not resend verification.') }
    finally { setBusy(false) }
  }
  if (pendingEmail) return <AuthLayout role={role} back={back}>
    <Card className="auth-card auth-state-card">
      <div className="auth-state-icon"><Mail aria-hidden="true" /></div>
      <h1>Check your email</h1>
      <p>We sent a secure verification link to <b>{pendingEmail}</b>. Verify your email before signing in and building your profile.</p>
      {message && <div className="success" role="status"><Check size={17} aria-hidden="true" />{message}</div>}
      {localVerificationUrl && <div className="local-email-preview"><b>Local development</b><span>Inbox delivery is not configured on this computer. Use this secure one-time link to continue testing.</span><a className="ui-button ui-button--primary ui-button--medium ui-button--full ui-button-link" href={localVerificationUrl}>Verify this local account</a></div>}
      <InlineError value={error} />
      <Button fullWidth onClick={resend} disabled={busy}>{busy ? 'Sending…' : 'Resend verification email'}</Button>
      <Button variant="ghost" fullWidth onClick={() => { setPendingEmail(''); setLocalVerificationUrl(''); setMode('login'); setMessage(''); setError('') }}>Back to login</Button>
    </Card>
  </AuthLayout>
  return <AuthLayout role={role} back={back}>
    <Card className="auth-card">
      <form className="auth-form" onSubmit={submit}>
        <Badge tone="neutral">{role === 'recruiter' ? 'RECRUITER WORKSPACE' : 'CANDIDATE PROFILE'}</Badge>
        <h1>{mode === 'signup' ? 'Create your account' : mode === 'forgot' ? 'Forgot your password?' : 'Welcome back'}</h1>
        <p>{mode === 'forgot' ? 'Enter your email. If an account exists, we’ll send a secure reset link.' : role === 'recruiter' ? 'Search real candidate profiles and build a thoughtful shortlist.' : 'Turn your resume into a profile you control.'}</p>
        <div className="auth-fields">
          {mode === 'signup' && <FormField label="Full name" name="full_name" required autoComplete="name" />}
          {mode === 'signup' && role === 'recruiter' && <FormField label="Company" name="company" required autoComplete="organization" />}
          <FormField label="Email" name="email" type="email" required autoComplete="email" />
          {mode !== 'forgot' && <FormField label="Password" name="password" type="password" minLength={8} required autoComplete={mode === 'signup' ? 'new-password' : 'current-password'} hint={mode === 'signup' ? 'Use at least 8 characters.' : undefined} />}
        </div>
        <InlineError value={error} />
        {message && <div className="success" role="status"><Check size={17} aria-hidden="true" />{message}</div>}
        <Button size="large" fullWidth disabled={busy}>{busy ? 'Please wait…' : mode === 'signup' ? 'Create account' : mode === 'forgot' ? 'Send reset link' : 'Log in'}</Button>
        {mode === 'login' && <Button type="button" variant="ghost" fullWidth onClick={() => { setMode('forgot'); setError(''); setMessage('') }}>Forgot password?</Button>}
        <Button type="button" variant="ghost" fullWidth onClick={() => { setMode(mode === 'signup' ? 'login' : mode === 'login' ? 'signup' : 'login'); setError(''); setMessage('') }}>
          {mode === 'signup' ? 'Already have an account? Log in' : mode === 'login' ? 'New here? Create an account' : 'Back to login'}
        </Button>
      </form>
    </Card>
  </AuthLayout>
}

function EmailVerificationScreen({ token, onDone }: { token: string; onDone: (payload: AuthPayload) => void }) {
  const started = useRef(false)
  const [error, setError] = useState('')
  useEffect(() => {
    if (started.current) return
    started.current = true
    api.verifyEmail(token).then(payload => {
      auth.save(payload)
      window.history.replaceState({}, '', '/')
      onDone(payload)
    }).catch(cause => setError(cause instanceof Error ? cause.message : 'This verification link could not be used.'))
  }, [token, onDone])
  return <AuthLayout role="candidate"><Card className="auth-card auth-state-card">
    <div className="auth-state-icon"><ShieldCheck aria-hidden="true" /></div>
    <h1>{error ? 'Verification link unavailable' : 'Verifying your email…'}</h1>
    <p role={error ? 'alert' : 'status'}>{error || 'One moment while we securely activate your candidate account.'}</p>
    {error && <a className="ui-button ui-button--primary ui-button--medium ui-button--full ui-button-link" href="/">Return to Enter</a>}
  </Card></AuthLayout>
}

function PasswordResetScreen({ token, done }: { token: string; done: () => void }) {
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [complete, setComplete] = useState(false)
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); setBusy(true); setError('')
    const data = Object.fromEntries(new FormData(event.currentTarget).entries()) as Record<string, string>
    if (data.password !== data.confirm_password) { setError('Passwords do not match.'); setBusy(false); return }
    try { await api.confirmPasswordReset(token, data.password); setComplete(true); window.history.replaceState({}, '', '/') }
    catch (cause) { setError(cause instanceof Error ? cause.message : 'This reset link could not be used.') }
    finally { setBusy(false) }
  }
  return <AuthLayout><Card className="auth-card auth-state-card">
    <div className="auth-state-icon"><ShieldCheck aria-hidden="true" /></div>
    <h1>{complete ? 'Password updated' : 'Choose a new password'}</h1>
    {complete ? <><p role="status">Your password has been changed and existing sessions have been signed out.</p><Button fullWidth onClick={done}>Continue to login</Button></>
      : <form className="nested-auth-form" onSubmit={submit}><p>Use a strong password you don’t use elsewhere.</p><FormField label="New password" name="password" type="password" minLength={8} required autoComplete="new-password" /><FormField label="Confirm password" name="confirm_password" type="password" minLength={8} required autoComplete="new-password" /><InlineError value={error} /><Button fullWidth disabled={busy}>{busy ? 'Updating…' : 'Reset password'}</Button></form>}
  </Card></AuthLayout>
}

function LegalPlaceholder({ kind }: { kind: 'privacy' | 'terms' }) {
  const title = kind === 'privacy' ? 'Privacy Policy' : 'Terms'
  return <main className="legal-page"><nav><Brand /><a href="/">Back to Enter</a></nav><article>
    <span>LEGAL REVIEW REQUIRED</span><h1>{title} placeholder</h1>
    <p>This page is intentionally a placeholder. It is not a legal policy and must be replaced with counsel-reviewed {title.toLowerCase()} before public launch.</p>
    <div><ShieldCheck /><p>Enter’s implemented product controls currently include private resume delivery, candidate-controlled visibility, backend authorization, account deletion, email verification, and recorded submission consent.</p></div>
  </article></main>
}

function Shell({ user, logout, children, noticeCount = 0 }: {
  user: User; logout: () => void; children: React.ReactNode; noticeCount?: number
}) {
  return <div className="app-shell">
    <header><Brand compact /><div className="header-user">
      {user.role === 'recruiter' && <span className="notification-pill"><Bell size={15} /> {noticeCount}</span>}
      <span>{user.full_name}</span><button onClick={logout} aria-label="Log out"><LogOut size={17} /></button>
    </div></header>
    {children}
  </div>
}

function CandidatePortal({ user, logout, accountDeleted }: { user: User; logout: () => void; accountDeleted: () => void }) {
  const [profile, setProfile] = useState<Candidate>(emptyProfile)
  const [experiences, setExperiences] = useState<WorkExperience[]>([])
  const [loading, setLoading] = useState(true)
  const [uploading, setUploading] = useState(false)
  const [draggingResume, setDraggingResume] = useState(false)
  const [message, setMessage] = useState('')
  const [error, setError] = useState('')
  const [editing, setEditing] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)
  const [wizardOpen, setWizardOpen] = useState(false)
  const [wizardModes, setWizardModes] = useState<string[]>([])
  const [reviewOpen, setReviewOpen] = useState(false)
  const [submitting, setSubmitting] = useState(false)
  const [consentChecked, setConsentChecked] = useState(false)
  const [deleteOpen, setDeleteOpen] = useState(false)
  const [deleting, setDeleting] = useState(false)
  const [deleteError, setDeleteError] = useState('')

  function applyProfile(next: Candidate) {
    setProfile(next)
    setExperiences(next.work_experiences)
  }

  useEffect(() => {
    api.candidateProfile()
      .then(applyProfile)
      .catch(e => setError(e.message))
      .finally(() => setLoading(false))
  }, [])

  useEffect(() => {
    const state = profile.latest_resume?.processing_status
    if (state !== 'queued' && state !== 'processing' && state !== 'uploaded') return
    let active = true
    const poll = async () => {
      try {
        const next = await api.candidateProfile()
        if (!active) return
        applyProfile(next)
        if (next.latest_resume?.processing_status === 'completed') {
          setMessage("We've built your starting profile. Take a look below.")
        }
      } catch (cause) {
        if (active) setError(cause instanceof Error ? cause.message : 'We could not refresh resume processing.')
      }
    }
    const interval = window.setInterval(poll, 1200)
    void poll()
    return () => { active = false; window.clearInterval(interval) }
  }, [profile.latest_resume?.id, profile.latest_resume?.processing_status])

  async function savePatch(patch: Partial<Candidate>, success = 'Saved to your profile.') {
    setError(''); setSaving(true)
    try {
      const next = await api.updateCandidate(patch)
      applyProfile(next)
      setMessage(success)
      return next
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'We could not save that change.')
      return null
    } finally { setSaving(false) }
  }

  async function upload(file?: File) {
    if (!file) return
    setUploading(true); setError(''); setMessage('')
    try {
      const next = await api.uploadResume(file)
      applyProfile(next)
      setMessage('Resume uploaded securely. Security scanning and profile extraction are queued.')
    }
    catch (e) { setError(e instanceof Error ? e.message : 'Upload failed.') }
    finally { setUploading(false) }
  }

  async function retryResume() {
    if (!profile.latest_resume) return
    setUploading(true); setError(''); setMessage('')
    try {
      applyProfile(await api.retryResume(profile.latest_resume.id))
      setMessage('Resume processing has been queued again.')
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'We could not retry resume processing.')
    } finally { setUploading(false) }
  }

  function openWizard() {
    setWizardModes(profile.work_preferences)
    setWizardOpen(true)
  }

  async function saveWizardValue(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const field = profile.missing_fields[0]
    if (!field) return setWizardOpen(false)
    const value = String(new FormData(event.currentTarget).get('value') || '').trim()
    let patch: Partial<Candidate>
    if (field.field === 'work_preferences') patch = { work_preferences: wizardModes }
    else if (field.field === 'skills') patch = { skills: value.split(',').map(item => item.trim()).filter(Boolean) }
    else if (field.field === 'education') patch = { education: value.split('\n').map(item => item.trim()).filter(Boolean) }
    else if (field.field === 'notice_period_days') patch = { notice_period_days: Number(value) }
    else if (field.field === 'total_experience') patch = { total_experience: value }
    else if (field.field === 'expected_salary_lpa') patch = { expected_salary_lpa: value }
    else patch = { [field.field]: value } as Partial<Candidate>
    const next = await savePatch(patch, 'Great — your profile is taking shape.')
    if (next && next.missing_fields.length === 0) setWizardOpen(false)
  }

  async function chooseNotice(days: number) {
    const next = await savePatch({ notice_period_days: days }, 'Notice period added.')
    if (next && next.missing_fields.length === 0) setWizardOpen(false)
  }

  async function chooseVisibility(value: Candidate['visibility']) {
    const next = await savePatch({ visibility: value }, 'Visibility preference added.')
    if (next && next.missing_fields.length === 0) setWizardOpen(false)
  }

  async function toggleWorkPreference(value: string) {
    const current = profile.work_preferences
    const next = current.includes(value) ? current.filter(item => item !== value) : [...current, value]
    await savePatch({ work_preferences: next }, 'Work preferences updated.')
  }

  function openReview() {
    setConsentChecked(Boolean(profile.submission_consent_at))
    setReviewOpen(true)
    window.setTimeout(() => document.querySelector('.review-submit')?.scrollIntoView({ behavior: 'smooth' }), 0)
  }

  async function submitProfile() {
    setSubmitting(true); setError('')
    try {
      const next = await api.submitCandidate(consentChecked)
      applyProfile(next)
      setReviewOpen(false)
      setMessage('Your profile has been submitted to Enter.')
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'We could not submit your profile.')
    } finally { setSubmitting(false) }
  }

  async function deleteAccount(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); setDeleting(true); setDeleteError('')
    const data = Object.fromEntries(new FormData(event.currentTarget).entries()) as Record<string, string>
    try {
      await api.deleteCandidateAccount(data.password, data.confirmation)
      auth.clear()
      accountDeleted()
    } catch (cause) {
      setDeleteError(cause instanceof Error ? cause.message : 'We could not delete your account.')
    } finally { setDeleting(false) }
  }

  const missing = profile.missing_fields[0]
  const completion = profile.profile_completion
  const recommendedMissing = profile.missing_fields.filter(item => item.category !== 'required')
  const visibilityOptions = [
    ['approved_recruiters', 'Visible to approved recruiters', 'Be discovered by trusted recruiters.'],
    ['matching_roles', 'Only matching roles', 'Appear only when the role aligns.'],
    ['not_looking', 'Not looking right now', 'Keep your profile, pause discovery.'],
  ] as const
  const workModes = ['Flexible', 'Remote', 'Hybrid', 'On-site']

  if (loading) return <Shell user={user} logout={logout}><main className="candidate-upload-first candidate-ui"><div className="candidate-profile-loading" role="status">Loading your profile…</div></main></Shell>

  const resumeState = profile.latest_resume?.processing_status
  if (profile.latest_resume && resumeState !== 'completed') return <Shell user={user} logout={logout}>
    <main className="candidate-upload-first candidate-ui">
      <CandidateWelcome />
      <CandidateProcessing resume={profile.latest_resume} uploading={uploading} retry={retryResume} upload={upload} error={error} />
    </main>
  </Shell>

  if (!profile.latest_resume) return <Shell user={user} logout={logout}>
    <main className="candidate-upload-first candidate-ui">
      <CandidateWelcome />
      <section className="candidate-upload-card" aria-labelledby="resume-upload-title">
        <div
          className={`cv-dropzone ${draggingResume ? 'dragging' : ''} ${uploading ? 'busy' : ''}`}
          onDragEnter={event => { event.preventDefault(); if (!uploading) setDraggingResume(true) }}
          onDragOver={event => { event.preventDefault(); if (!uploading) setDraggingResume(true) }}
          onDragLeave={event => { if (!event.currentTarget.contains(event.relatedTarget as Node)) setDraggingResume(false) }}
          onDrop={event => { event.preventDefault(); setDraggingResume(false); if (!uploading) void upload(event.dataTransfer.files?.[0]) }}
        >
          <div className="cv-mark">CV</div>
          <div className="cv-drop-content">
            <h2 id="resume-upload-title">{uploading ? 'Uploading your resume…' : 'Drop your resume'}</h2>
            <p>{uploading ? 'Your private file is being stored securely before processing begins.' : 'Drag and drop your CV here, or choose it from your device.'}</p>
            <label className={`cv-file-button ${uploading ? 'busy' : ''}`}><input type="file" aria-label="Choose PDF or DOCX resume" accept=".pdf,.docx" onChange={event => upload(event.target.files?.[0])} disabled={uploading} data-testid="resume-input" /><UploadCloud size={18} /><span>{uploading ? 'Uploading…' : 'Choose PDF or DOCX'}</span></label>
            <small>PDF or DOCX · Maximum 5 MB</small>
          </div>
        </div>
        <InlineError value={error} />
        <div className="candidate-upload-points">
          <div><span>RECRUITERS SEE</span><b>Role, skills, notice, compensation, and proof of work</b></div>
          <div><span>YOU CONTROL</span><b>Visibility, work mode, and outreach preference</b></div>
          <div><span>AFTER UPLOAD</span><b>Only missing details are shown for confirmation</b></div>
        </div>
      </section>
    </main>
  </Shell>

  return <Shell user={user} logout={logout}>
    <main className="candidate-studio candidate-ui">
      <section className="studio-hero">
        <CandidateWelcome />
        {profile.latest_resume && <div className="completion-card" aria-label="Profile completion"><div className="completion-ring" style={{ '--completion': `${completion.percent * 3.6}deg` } as React.CSSProperties}><span>{completion.percent}%</span></div><div><b>{completion.remaining ? 'Your profile is almost ready' : 'Your profile is ready'}</b><span>{completion.remaining ? `${completion.remaining} ${completion.remaining === 1 ? 'detail' : 'details'} left` : 'Everything important is in place'}</span></div></div>}
      </section>

      <section className={`resume-launch ${profile.latest_resume ? 'has-resume' : ''}`}>
        <div className="resume-launch-copy"><div className="resume-icon"><FileText /></div><div><span>{profile.latest_resume ? 'YOUR RESUME' : 'START HERE'}</span><h2>{profile.latest_resume ? "We've built your starting profile" : 'Upload your resume'}</h2><p>{profile.latest_resume ? 'Review what we found and add the details that make your story yours.' : 'PDF or DOCX. We’ll turn it into a profile you can review and edit.'}</p></div></div>
        <label className={`resume-action ${uploading ? 'busy' : ''}`}><input type="file" aria-label="Upload a newer resume" accept=".pdf,.docx" onChange={event => upload(event.target.files?.[0])} disabled={uploading} data-testid="resume-input" /><UploadCloud size={19} /><span>{uploading ? 'Uploading your resume…' : profile.latest_resume ? 'Upload a newer resume' : 'Choose your resume'}</span></label>
        {profile.latest_resume && <div className="resume-file"><span><Check size={15} />{profile.latest_resume.original_name}<small>Version {profile.latest_resume.version}</small></span>{profile.latest_resume.url && <a href={profile.latest_resume.url} aria-label="Download resume"><Download size={16} /></a>}</div>}
      </section>

      <div className="candidate-notices"><InlineError value={error} />{message && <div className="success"><Check size={17} />{message}</div>}</div>

      {!profile.latest_resume && !loading && <section className="before-profile"><div><Zap /><b>A thoughtful starting point</b><span>We extract what your resume actually says.</span></div><div><Pencil /><b>Easy to shape</b><span>Edit each profile section when you’re ready.</span></div><div><ShieldCheck /><b>You choose visibility</b><span>Your resume stays private and follows your preferences.</span></div></section>}

      {profile.latest_resume && profile.missing_fields.length > 0 && <section className="missing-callout"><div className="missing-callout-icon"><Sparkles /></div><div><span>A FEW QUICK DETAILS</span><h2>Your resume gave us a great start.</h2><p>We need {completion.remaining} more {completion.remaining === 1 ? 'detail' : 'details'} to complete your profile.</p><div className="missing-preview">{profile.missing_fields.slice(0, 3).map(item => <span key={item.field}><Target size={13} /><small>{item.category}</small>{item.message}</span>)}</div></div><button className="primary" onClick={openWizard}>Complete my profile <ArrowRight size={16} /></button></section>}

      {wizardOpen && missing && <section className="quick-step" aria-live="polite"><button className="quick-step-close" onClick={() => setWizardOpen(false)} aria-label="Close quick completion"><X /></button><div className="quick-step-count">{missing.category.toUpperCase()} · {completion.remaining} LEFT</div><h2>{missing.prompt}</h2><p>{missing.field === 'meaningful_work' ? 'Tell recruiters about a project, product, system, research project, or piece of work you’re especially proud of.' : missing.message}</p>
        {missing.field === 'notice_period_days' ? <div className="choice-row">{[0, 15, 30, 60, 90].map(days => <button key={days} onClick={() => chooseNotice(days)}>{days === 0 ? 'Immediate' : days === 90 ? '90+ days' : `${days} days`}</button>)}</div>
          : missing.field === 'visibility' ? <div className="visibility-grid quick-visibility">{visibilityOptions.map(([value, title, copy]) => <button key={value} onClick={() => chooseVisibility(value)}><span className="visibility-icon">{value === 'not_looking' ? <EyeOff /> : <Eye />}</span><b>{title}</b><small>{copy}</small></button>)}</div>
            : missing.field === 'work_experiences' ? <button className="primary" onClick={() => { setEditing('experience'); setWizardOpen(false) }}>Add my experience <ArrowRight size={16} /></button>
            : <form onSubmit={saveWizardValue} className="quick-step-form">
              {missing.field === 'work_preferences' ? <div className="choice-row multi">{workModes.map(mode => <button type="button" key={mode} className={wizardModes.includes(mode) ? 'selected' : ''} aria-pressed={wizardModes.includes(mode)} onClick={() => setWizardModes(old => old.includes(mode) ? old.filter(item => item !== mode) : [...old, mode])}>{wizardModes.includes(mode) && <Check size={14} />}{mode}</button>)}</div>
                : missing.field === 'meaningful_work' ? <div className="proud-input"><textarea name="value" aria-label={missing.label} required rows={5} defaultValue={profile.meaningful_work} placeholder="What did you build? What was your contribution? What impact did it have?" /><span>A few thoughtful sentences are plenty.</span></div>
                  : missing.field === 'education' ? <div className="proud-input"><textarea name="value" aria-label={missing.label} required rows={4} defaultValue={profile.education.join('\n')} placeholder="Degree, institution, and graduation year" /><span>One qualification per line works well.</span></div>
                  : <input name="value" aria-label={missing.label} required type={['total_experience', 'expected_salary_lpa'].includes(missing.field) ? 'number' : missing.field.includes('url') ? 'url' : 'text'} step={missing.field === 'total_experience' ? '0.1' : undefined} placeholder={missing.field === 'skills' ? 'Python, Django, PostgreSQL' : `Add your ${missing.label}`} />}
              <button className="primary" disabled={missing.field === 'work_preferences' && wizardModes.length === 0}>Save and continue <ArrowRight size={16} /></button>
              {missing.category !== 'required' && <button type="button" className="skip-detail" onClick={() => setWizardOpen(false)}>Skip for now</button>}
            </form>}
      </section>}

      {profile.latest_resume && !loading && <div className={`profile-board ${saving ? 'saving' : ''}`} aria-busy={saving}>
        <section className="profile-section about-card"><div className="profile-section-head"><div><span>ABOUT YOU</span><h2>{profile.full_name}</h2></div><button onClick={() => setEditing(editing === 'about' ? null : 'about')}><Pencil size={15} /> Edit</button></div>
          {editing === 'about' ? <form className="card-edit-grid" onSubmit={async event => { event.preventDefault(); const data = Object.fromEntries(new FormData(event.currentTarget).entries()) as Record<string, string>; const next = await savePatch({ full_name: data.full_name, headline: data.headline, current_company: data.current_company, location: data.location, total_experience: data.total_experience, summary: data.summary }, 'About you updated.'); if (next) setEditing(null) }}><label>Full name<input name="full_name" defaultValue={profile.full_name} required /></label><label>Current role<input name="headline" defaultValue={profile.headline} /></label><label>Company<input name="current_company" defaultValue={profile.current_company} /></label><label>Location<input name="location" defaultValue={profile.location} /></label><label>Experience<input name="total_experience" type="number" step="0.1" defaultValue={profile.total_experience} /></label><label className="wide">Short introduction<textarea name="summary" rows={3} defaultValue={profile.summary} /></label><div className="card-edit-actions"><button type="button" onClick={() => setEditing(null)}>Cancel</button><button className="primary">Save</button></div></form>
            : <><p className="profile-headline">{profile.headline || 'Add your current role'} {profile.current_company && <span>at {profile.current_company}</span>}</p><div className="profile-fact-chips"><span><MapPin size={14} />{profile.location || 'Add location'}</span><span><BriefcaseBusiness size={14} />{Number(profile.total_experience) ? `${profile.total_experience} years` : 'Add experience'}</span><span>{profile.notice_period_days == null ? 'Add notice period' : profile.notice_period_days === 0 ? 'Available immediately' : `${profile.notice_period_days} days notice`}</span></div>{profile.summary && <p className="profile-summary">{profile.summary}</p>}</>}
        </section>

        <section className="profile-section skills-card"><div className="profile-section-head"><div><span>SKILLS</span><h2>What you work with</h2></div></div><div className="editable-chips">{profile.skills.map(skill => <button key={skill} title={`Remove ${skill}`} aria-label={`Remove ${skill}`} onClick={() => savePatch({ skills: profile.skills.filter(item => item !== skill) }, `${skill} removed.`)}>{skill}<X size={13} /></button>)}<form onSubmit={async event => { event.preventDefault(); const form = event.currentTarget; const input = form.elements.namedItem('skill') as HTMLInputElement; const skill = input.value.trim(); if (skill && !profile.skills.includes(skill)) { await savePatch({ skills: [...profile.skills, skill] }, `${skill} added.`); form.reset() } }}><input name="skill" aria-label="Add skill" placeholder="Add a skill" /><button aria-label="Save skill"><Plus size={15} /></button></form></div></section>

        <section className="profile-section experience-card"><div className="profile-section-head"><div><span>EXPERIENCE</span><h2>Your career story</h2></div><button onClick={() => setEditing(editing === 'experience' ? null : 'experience')}><Pencil size={15} /> {editing === 'experience' ? 'Done' : 'Edit'}</button></div>
          {editing === 'experience' ? <div className="experience-editor"><button className="add-row" type="button" onClick={() => setExperiences(old => [...old, { company: '', role: '', start_date: '', end_date: null, description: '', gap_reason: '' }])}><Plus size={15} /> Add experience</button>{experiences.map((item, index) => <div className="experience-edit-row" key={item.id ?? index}><label>Company<input aria-label={`Experience company ${index + 1}`} required value={item.company} onChange={event => setExperiences(old => old.map((value, position) => position === index ? { ...value, company: event.target.value } : value))} /></label><label>Role<input aria-label={`Experience role ${index + 1}`} required value={item.role} onChange={event => setExperiences(old => old.map((value, position) => position === index ? { ...value, role: event.target.value } : value))} /></label><label>Start<input aria-label={`Experience start ${index + 1}`} type="date" required value={item.start_date} onChange={event => setExperiences(old => old.map((value, position) => position === index ? { ...value, start_date: event.target.value } : value))} /></label><label>End<input aria-label={`Experience end ${index + 1}`} type="date" value={item.end_date || ''} onChange={event => setExperiences(old => old.map((value, position) => position === index ? { ...value, end_date: event.target.value || null } : value))} /></label><label className="experience-description">Highlights<input aria-label={`Experience highlights ${index + 1}`} value={item.description} onChange={event => setExperiences(old => old.map((value, position) => position === index ? { ...value, description: event.target.value } : value))} /></label><label className="experience-gap-reason">Reason for the gap before this role<input aria-label={`Gap reason before experience ${index + 1}`} value={item.gap_reason || ''} placeholder="For example: further study or caregiving" onChange={event => setExperiences(old => old.map((value, position) => position === index ? { ...value, gap_reason: event.target.value } : value))} /></label><button type="button" aria-label={`Remove experience ${index + 1}`} onClick={() => setExperiences(old => old.filter((_, position) => position !== index))}><Trash2 size={15} /></button></div>)}<div className="card-edit-actions"><button onClick={() => { setExperiences(profile.work_experiences); setEditing(null) }}>Cancel</button><button className="primary" onClick={async () => { const next = await savePatch({ work_experiences: experiences }, 'Experience updated.'); if (next) setEditing(null) }}>Save experience</button></div></div>
            : <div className="experience-list">{profile.work_experiences.length ? [...profile.work_experiences].reverse().map(item => <article key={item.id}><div className="experience-mark" /><div><small>{item.start_date.slice(0, 7)} — {item.end_date?.slice(0, 7) || 'Present'}</small><h3>{item.role}</h3><b>{item.company}</b>{item.description && <p>{item.description}</p>}</div></article>) : <button className="empty-section" onClick={() => setEditing('experience')}><Plus /> Add your recent experience</button>}</div>}
        </section>

        <section className="profile-section education-card"><div className="profile-section-head"><div><span>EDUCATION</span><h2>Learning that shaped you</h2></div><button onClick={() => setEditing(editing === 'education' ? null : 'education')}><Pencil size={15} /> Edit</button></div>{editing === 'education' ? <form onSubmit={async event => { event.preventDefault(); const value = String(new FormData(event.currentTarget).get('education') || ''); const next = await savePatch({ education: value.split('\n').map(item => item.trim()).filter(Boolean) }, 'Education updated.'); if (next) setEditing(null) }}><textarea aria-label="Education" name="education" rows={4} defaultValue={profile.education.join('\n')} placeholder="One qualification per line" /><div className="card-edit-actions"><button type="button" onClick={() => setEditing(null)}>Cancel</button><button className="primary">Save</button></div></form> : profile.education.length ? <div className="education-list">{profile.education.map(item => <span key={item}><GraduationCap />{item}</span>)}</div> : <button className="empty-section" onClick={() => setEditing('education')}><Plus /> Add education</button>}</section>

        <section className="profile-section proud-card"><div className="proud-badge"><Sparkles /></div><span>BEYOND THE RESUME</span><h2>What’s the most meaningful thing you’ve built?</h2><p>Tell recruiters about a project, product, system, research project, or piece of work you’re especially proud of.</p>{editing === 'meaningful' || !profile.meaningful_work ? <form onSubmit={async event => { event.preventDefault(); const value = String(new FormData(event.currentTarget).get('meaningful_work') || ''); const next = await savePatch({ meaningful_work: value }, 'Meaningful work added.'); if (next) setEditing(null) }}><div className="proud-input"><textarea aria-label="Meaningful work" name="meaningful_work" rows={6} defaultValue={profile.meaningful_work} placeholder="What did you build? What was your contribution? What impact did it have?" /><span>A few thoughtful sentences are plenty.</span></div><button className="primary">Save my answer</button></form> : <div className="proud-answer"><p>{profile.meaningful_work}</p><button onClick={() => setEditing('meaningful')}><Pencil size={14} /> Edit answer</button></div>}</section>

        <section className="profile-section preferences-card"><div className="profile-section-head"><div><span>OPPORTUNITY PREFERENCES</span><h2>How recruiters can find you</h2><p>Decide how recruiters can discover and approach you.</p></div></div><h3>Profile visibility</h3><div className="visibility-grid">{visibilityOptions.map(([value, title, copy]) => <button key={value} className={profile.visibility === value ? 'selected' : ''} aria-pressed={profile.visibility === value} onClick={() => savePatch({ visibility: value }, 'Visibility updated.')}><span className="visibility-icon">{value === 'not_looking' ? <EyeOff /> : <Eye />}</span><b>{title}</b><small>{copy}</small>{profile.visibility === value && <Check className="selected-check" />}</button>)}</div><h3>Work preferences</h3><div className="work-mode-row">{workModes.map(mode => <button key={mode} className={profile.work_preferences.includes(mode) ? 'selected' : ''} aria-pressed={profile.work_preferences.includes(mode)} onClick={() => toggleWorkPreference(mode)}>{profile.work_preferences.includes(mode) && <Check size={14} />}{mode}</button>)}</div>{profile.visibility === 'not_looking' && <p className="paused-note"><ShieldCheck size={15} />Your profile is saved, but recruiters won’t see it in search while you’re paused.</p>}</section>

        <section className="profile-section contact-card"><div className="profile-section-head"><div><span>LINKS & CONTACT</span><h2>Make it easy to learn more</h2></div><button onClick={() => setEditing(editing === 'contact' ? null : 'contact')}><Pencil size={15} /> Edit</button></div>{editing === 'contact' ? <form className="card-edit-grid" onSubmit={async event => { event.preventDefault(); const data = Object.fromEntries(new FormData(event.currentTarget).entries()) as Record<string, string>; const next = await savePatch({ email: data.email, phone: data.phone, linkedin_url: data.linkedin_url, github_url: data.github_url, expected_salary_lpa: data.expected_salary_lpa || null }, 'Contact details updated.'); if (next) setEditing(null) }}><label>Email<input name="email" type="email" defaultValue={profile.email} /></label><label>Phone / WhatsApp<input name="phone" defaultValue={profile.phone} /></label><label>LinkedIn<input name="linkedin_url" type="url" defaultValue={profile.linkedin_url} /></label><label>GitHub / portfolio<input name="github_url" type="url" defaultValue={profile.github_url} /></label><label>Expected compensation (LPA)<input name="expected_salary_lpa" type="number" step="0.01" defaultValue={profile.expected_salary_lpa || ''} /></label><div className="card-edit-actions"><button type="button" onClick={() => setEditing(null)}>Cancel</button><button className="primary">Save</button></div></form> : <div className="contact-links"><span><Mail />{profile.email || 'Add email'}</span><span><MessageCircle />{profile.phone || 'Add phone'}</span><span><Link />{profile.linkedin_url ? 'LinkedIn added' : 'Add LinkedIn'}</span><span><Code2 />{profile.github_url ? 'GitHub added' : 'Add GitHub'}</span></div>}</section>
      </div>}

      {profile.latest_resume && !loading && (profile.profile_status === 'submitted'
        ? <section className="submission-stage submitted"><div className="submission-mark"><CheckCircle2 /></div><div><span>PROFILE SUBMITTED</span><h2>You’re all set!</h2><p>Your profile has been submitted to Enter. We’ll use your preferences to connect you with relevant opportunities.</p>{profile.submitted_at && <small>Submitted {new Date(profile.submitted_at).toLocaleString()}</small>}{profile.visibility === 'not_looking' && <p className="submission-visibility-note">Your profile remains submitted, but discovery is paused while you’re not looking.</p>}</div><button onClick={() => document.querySelector('.profile-board')?.scrollIntoView({ behavior: 'smooth' })}><Pencil size={15} /> Edit my profile</button></section>
        : <section className="submission-stage"><div className="submission-mark"><Target /></div><div><span>FINAL STEP</span><h2>Ready for a final look?</h2><p>Review the profile recruiters will see, confirm your preferences, then submit when it feels right.</p></div><button className="primary" onClick={openReview}>Review &amp; submit <ArrowRight size={16} /></button></section>)}

      {reviewOpen && profile.profile_status === 'draft' && <section className="review-submit">
        <div className="review-submit-head"><div><span>REVIEW &amp; SUBMIT</span><h2>Your professional story, at a glance.</h2><p>Required details keep your profile useful. Recommended details add context but never block submission.</p></div><button aria-label="Close review" onClick={() => setReviewOpen(false)}><X /></button></div>
        <div className="review-snapshot"><div><FileText /><span><small>Resume</small><b>{profile.latest_resume?.original_name}</b></span></div><div><BriefcaseBusiness /><span><small>Career journey</small><b>{profile.work_experiences.length ? `${profile.work_experiences.length} roles` : 'Not added'}</b></span></div><div><GraduationCap /><span><small>Education</small><b>{profile.education.length ? `${profile.education.length} entries` : 'Not added'}</b></span></div><div><Sparkles /><span><small>Skills</small><b>{profile.skills.length ? profile.skills.slice(0, 3).join(', ') : 'Not added'}</b></span></div></div>
        <div className="review-requirements"><div><h3>Required before submission</h3>{profile.submission_missing_fields.length ? profile.submission_missing_fields.map(item => <button key={item.field} onClick={() => { setReviewOpen(false); setWizardOpen(true) }}><Target /><span><b>{item.label}</b><small>{item.message}</small></span><ArrowRight /></button>) : <p className="requirement-ready"><CheckCircle2 /> All required details are ready.</p>}</div><div><h3>Recommended, not required</h3>{recommendedMissing.length ? <ul>{recommendedMissing.map(item => <li key={item.field}>{item.label}</li>)}</ul> : <p className="requirement-ready"><CheckCircle2 /> Your supporting details are complete.</p>}</div></div>
        <label className="submission-consent"><input type="checkbox" checked={consentChecked} onChange={event => setConsentChecked(event.target.checked)} /><span><b>Profile-sharing consent</b>By submitting your profile, you agree that Enter may make your profile available to recruiters according to your visibility preferences. Your profile and resume are not visible to other candidates.<small><a href="/privacy" target="_blank">Privacy Policy</a><span>·</span><a href="/terms" target="_blank">Terms</a></small></span></label>
        <div className="review-submit-actions"><button onClick={() => setReviewOpen(false)}>Keep editing</button><button className="primary" onClick={submitProfile} disabled={!profile.can_submit || !consentChecked || submitting}>{submitting ? 'Submitting…' : 'Submit my profile'} <ArrowRight size={16} /></button></div>
      </section>}

      {profile.latest_resume && !loading && <section className="account-controls"><div><span>ACCOUNT &amp; PRIVACY</span><h2>Your profile stays in your control.</h2><p>You can pause discovery at any time. Deleting your account permanently removes your profile, resume files, recruiter signals, and account access.</p></div>{deleteOpen ? <form onSubmit={deleteAccount}><label>Current password<input name="password" type="password" required autoComplete="current-password" /></label><label>Type DELETE to confirm<input name="confirmation" required autoComplete="off" /></label><InlineError value={deleteError} /><div><button type="button" onClick={() => { setDeleteOpen(false); setDeleteError('') }}>Cancel</button><button className="danger-button" disabled={deleting}>{deleting ? 'Deleting…' : 'Permanently delete my account'}</button></div></form> : <button className="delete-account-trigger" onClick={() => setDeleteOpen(true)}><Trash2 size={16} /> Delete my account</button>}</section>}
    </main>
  </Shell>
}

function formatMonths(startValue: string, endValue: string | null) {
  const start = new Date(startValue)
  const end = endValue ? new Date(endValue) : new Date()
  if (Number.isNaN(start.getTime()) || Number.isNaN(end.getTime()) || end < start) return ''
  const months = Math.max(1, Math.round((end.getTime() - start.getTime()) / 2629800000))
  return months >= 12 ? `${(months / 12).toFixed(months % 12 ? 1 : 0)} yrs` : `${months} mo`
}

function monthsBetween(startValue: string, endValue: string | null) {
  const start = new Date(startValue)
  const end = endValue ? new Date(endValue) : new Date()
  if (Number.isNaN(start.getTime()) || Number.isNaN(end.getTime()) || end <= start) return 1
  return Math.max(1, Math.round((end.getTime() - start.getTime()) / 2629800000))
}

function CareerJourney({ items, detailed = false }: { items: WorkExperience[]; detailed?: boolean }) {
  const sorted = [...items].sort((a, b) => a.start_date.localeCompare(b.start_date))
  if (!sorted.length) return <p className="muted">No employment history has been confirmed yet.</p>
  return <div className={`career-journey ${detailed ? 'detailed' : 'compact'}`} aria-label="Career journey" role="list">
    {sorted.map((item, index) => {
      const previous = sorted[index - 1]
      const gapMilliseconds = previous?.end_date
        ? new Date(item.start_date).getTime() - new Date(previous.end_date).getTime()
        : 0
      const hasGap = Boolean(previous?.end_date) && Number.isFinite(gapMilliseconds) && gapMilliseconds > 60 * 86400000
      const gapMonths = hasGap ? Math.round(gapMilliseconds / 2629800000) : 0
      const duration = formatMonths(item.start_date, item.end_date)
      return <div key={`${item.company}-${item.start_date}`} className="career-sequence">
        {hasGap && <div className="career-gap-period" role="listitem" tabIndex={0} style={{ flexGrow: Math.max(1, gapMonths) }} aria-label={`Career gap of approximately ${gapMonths} months. ${item.gap_reason || 'Reason not provided by candidate.'}`}><b>{gapMonths >= 12 ? `${Math.round(gapMonths / 12)} yr gap` : `${gapMonths} mo gap`}</b><span className="career-period-line" /><small>{previous.end_date?.slice(0, 4)}<i>{item.start_date.slice(0, 4)}</i></small><span className="career-detail gap-detail"><b>Career gap</b><small>{gapMonths >= 12 ? `Approximately ${Math.round(gapMonths / 12)} year${Math.round(gapMonths / 12) === 1 ? '' : 's'}` : `Approximately ${gapMonths} months`}</small><span>{item.gap_reason || 'Reason not provided by the candidate.'}</span></span></div>}
        <div className="career-period" role="listitem" style={{ flexGrow: monthsBetween(item.start_date, item.end_date) }}>
          <button type="button" className="career-job" aria-label={`${item.role} at ${item.company}, ${item.start_date} to ${item.end_date || 'present'}${duration ? `, ${duration}` : ''}`}>
            <b>{item.company}</b><span className="career-period-line"><i /><i /></span><small><span>{index === 0 || hasGap ? item.start_date.slice(0, 4) : ''}</span><i>{item.end_date?.slice(0, 4) || 'Now'}</i></small>{detailed && <em>{item.role}</em>}
            <span className="career-detail"><b>{item.role}</b><small>{item.company}</small><span>{item.start_date.slice(0, 7)} — {item.end_date?.slice(0, 7) || 'Present'}{duration && ` · ${duration}`}</span>{item.description && <p>{item.description}</p>}</span>
          </button>
        </div>
      </div>
    })}
  </div>
}

function CandidateCard({ result, selected, toggle, open, status }: {
  result: SearchResult; selected: boolean; toggle: () => void; open: () => void; status: (value: string) => void
}) {
  const candidate = result.candidate
  const whatsapp = candidate.phone ? `https://wa.me/${candidate.phone.replace(/\D/g, '')}` : ''
  return <article className={`candidate-card ${selected ? 'selected' : ''}`}>
    <div className="candidate-main">
      <div className="candidate-top">
        <div className="avatar">{candidate.full_name.split(' ').map(v => v[0]).join('').slice(0, 2)}</div>
        <div><div className="name-row"><h3>{candidate.full_name}</h3>{candidate.viewed && <span className="signal viewed">Viewed</span>}{candidate.update_label && <span className="signal updated">{candidate.update_label}</span>}</div>
          <p>{candidate.headline || 'Role not specified'} {candidate.current_company && `at ${candidate.current_company}`}</p>
          {candidate.education[0] && <p className="candidate-education">{candidate.education[0]}</p>}
        </div>
      </div>
      <div className="candidate-facts">
        <span><MapPin /> <b>Location:</b> {candidate.location || 'Not shared'}</span>
        <span><CalendarDays /> <b>Notice period:</b> {candidate.notice_period_days == null ? '—' : candidate.notice_period_days === 0 ? 'Immediate' : `${candidate.notice_period_days} days`}</span>
        <span><BriefcaseBusiness /> <b>Experience:</b> {candidate.total_experience} years</span>
        <span><IndianRupee /> <b>{candidate.current_salary_lpa ? 'Current salary:' : 'Expected salary:'}</b> {candidate.current_salary_lpa || candidate.expected_salary_lpa ? `${candidate.current_salary_lpa || candidate.expected_salary_lpa} LPA` : 'Not shared'}</span>
      </div>
      <div className="career-row"><b>career journey</b><CareerJourney items={candidate.work_experiences} /></div>
      <div className="card-skills"><b>Skills</b><div className="skill-list">{candidate.skills.slice(0, 7).map(skill => <span key={skill}><Check />{skill}</span>)}</div></div>
    </div>
    <div className="candidate-actions">
      <label className="compare-check"><input type="checkbox" checked={selected} onChange={toggle} /> Compare</label>
      <label className="card-stage-label">Hiring stage
      <select className={`stage-select ${candidate.stage === 'non_relevant' || candidate.stage === 'rejected' ? 'stage-closed' : candidate.stage ? 'stage-active' : ''}`} aria-label={`Stage for ${candidate.full_name}`} value={candidate.stage || ''} onChange={e => status(e.target.value)}>
        <option value="">Set stage</option>{recruiterStages.map(([value, label]) => <option key={value} value={value}>{label}</option>)}
      </select></label>
      {(candidate.email || whatsapp) && <div className="contact-icon-row">{whatsapp && <a href={whatsapp} target="_blank" rel="noreferrer" aria-label={`WhatsApp ${candidate.full_name}`} title="WhatsApp"><MessageCircle /></a>}{candidate.email && <a href={`mailto:${candidate.email}`} aria-label={`Email ${candidate.full_name}`} title="Email"><Mail /></a>}</div>}
      <button className="primary small" onClick={open}>View profile</button>
      {(candidate.work_preferences.length > 0 || candidate.employment_type) && <div className="stage-signals"><b>Preference signals</b><div>{candidate.work_preferences.slice(0, 2).map(preference => <span key={preference}>{preference}</span>)}{candidate.employment_type && <span>{candidate.employment_type}</span>}</div></div>}
    </div>
  </article>
}

function NonRelevantDialog({ candidateName, reasons, note, saving, toggleReason, setNote, cancel, save }: {
  candidateName: string
  reasons: string[]
  note: string
  saving: boolean
  toggleReason: (reason: string) => void
  setNote: (note: string) => void
  cancel: () => void
  save: (event: FormEvent) => void
}) {
  const dialogRef = useDialogFocus(cancel)
  return <div className="overlay non-relevant-overlay recruiter-results-ui" role="presentation">
    <form ref={dialogRef as React.RefObject<HTMLFormElement>} tabIndex={-1} className="non-relevant-modal" role="dialog" aria-modal="true" aria-labelledby="non-relevant-title" onSubmit={save}>
      <h2 id="non-relevant-title">Why is {candidateName} not relevant?</h2>
      <p>This helps improve future result quality for recruiters.</p>
      <fieldset><legend className="sr-only">Select all reasons that apply</legend><div className="non-relevant-reasons">
        {nonRelevantOptions.map(reason => <label key={reason} className={reasons.includes(reason) ? 'selected' : ''}><input type="checkbox" checked={reasons.includes(reason)} onChange={() => toggleReason(reason)} /><span>{reason}</span></label>)}
      </div></fieldset>
      <label className="non-relevant-note"><span className="sr-only">Additional feedback</span><textarea value={note} onChange={event => setNote(event.target.value)} placeholder="Add a short note for the search quality team…" maxLength={1000} /></label>
      <div className="non-relevant-actions"><button type="button" onClick={cancel}>Cancel</button><button className="primary" disabled={saving || (reasons.length === 0 && !note.trim())}>{saving ? 'Saving…' : 'Save feedback'}</button></div>
    </form>
  </div>
}

function ProfileDrawer({ candidate, close, refresh, projects, selectedProject, addToProject }: {
  candidate: Candidate; close: () => void; refresh: () => void; projects: Project[]
  selectedProject: number | null; addToProject: (projectId: number, candidateId: number) => void
}) {
  const dialogRef = useDialogFocus(close)
  const whatsapp = candidate.phone ? `https://wa.me/${candidate.phone.replace(/\D/g, '')}` : ''
  const [projectId, setProjectId] = useState(String(selectedProject || projects[0]?.id || ''))
  const facts = [
    candidate.location && ['Location', candidate.location],
    Number(candidate.total_experience) > 0 && ['Experience', `${candidate.total_experience} years`],
    candidate.notice_period_days != null && ['Notice', candidate.notice_period_days === 0 ? 'Immediate' : `${candidate.notice_period_days} days`],
    candidate.current_salary_lpa && ['Current compensation', `₹${candidate.current_salary_lpa} LPA`],
    candidate.expected_salary_lpa && ['Expected compensation', `₹${candidate.expected_salary_lpa} LPA`],
    candidate.employment_type && ['Employment', candidate.employment_type],
  ].filter(Boolean) as string[][]
  return <div ref={dialogRef as React.RefObject<HTMLDivElement>} tabIndex={-1} className="overlay recruiter-results-ui" role="dialog" aria-modal="true" aria-label="Candidate profile"><div className="profile-drawer">
    <button className="close" aria-label="Close candidate profile" onClick={close}><X /></button>
    <div className="profile-hero"><div className="avatar large">{candidate.full_name.split(' ').map(v => v[0]).join('').slice(0, 2)}</div><div><div className="eyebrow">CANDIDATE PROFILE · SUBMITTED · VIEWED</div><h2>{candidate.full_name}</h2><p>{candidate.headline} {candidate.current_company && `at ${candidate.current_company}`}</p></div></div>
    <div className="profile-actions">
      {candidate.linkedin_url && /^https?:\/\//i.test(candidate.linkedin_url) && <a className="icon-action" href={candidate.linkedin_url} target="_blank" rel="noopener noreferrer" aria-label="LinkedIn" title="LinkedIn"><LinkedInMark /></a>}
      {candidate.github_url && /^https?:\/\//i.test(candidate.github_url) && <a className="icon-action" href={candidate.github_url} target="_blank" rel="noopener noreferrer" aria-label="GitHub" title="GitHub"><GithubMark /></a>}
      {candidate.email && <a className="icon-action" href={`mailto:${candidate.email}`} aria-label="Email" title="Email"><Mail /></a>}
      {whatsapp && <a className="icon-action" href={whatsapp} target="_blank" rel="noreferrer" aria-label="WhatsApp" title="WhatsApp"><MessageCircle /></a>}
    </div>
    <ResumeAccess resume={candidate.latest_resume} />
    {projects.length > 0 && <div className="profile-project-action"><FolderPlus /><div><b>Add to a project</b><span>Keep this candidate with the search context.</span></div><select aria-label="Profile project" value={projectId} onChange={event => setProjectId(event.target.value)}>{projects.map(project => <option key={project.id} value={project.id}>{project.name}</option>)}</select><button className="primary small" disabled={!projectId} onClick={() => addToProject(Number(projectId), candidate.id)}>Add</button></div>}
    {facts.length > 0 && <div className="profile-facts">{facts.map(([label, value]) => <div key={label}><span>{label}</span><b>{value}</b></div>)}</div>}
    {candidate.summary && <section><div className="section-kicker">ABOUT</div><p>{candidate.summary}</p></section>}
    {candidate.meaningful_work && <section><div className="section-kicker">MEANINGFUL WORK</div><p className="meaningful-profile-copy">{candidate.meaningful_work}</p></section>}
    {candidate.skills.length > 0 && <section><div className="section-kicker">SKILLS</div><div className="skill-list">{candidate.skills.map(skill => <span key={skill}>{skill}</span>)}</div></section>}
    {candidate.work_preferences.length > 0 && <section><div className="section-kicker">WORK PREFERENCES</div><div className="skill-list">{candidate.work_preferences.map(preference => <span key={preference}>{preference}</span>)}</div></section>}
    {candidate.education.length > 0 && <section><div className="section-kicker">EDUCATION</div><div className="profile-education">{candidate.education.map(item => <p key={item}><GraduationCap /> {item}</p>)}</div></section>}
    {candidate.work_experiences.length > 0 && <section><div className="section-kicker">CAREER JOURNEY</div><CareerJourney items={candidate.work_experiences} detailed /></section>}
    <button className="text-button" onClick={refresh}>Refresh persisted signals</button>
  </div></div>
}

function CompareModal({ candidates, close }: { candidates: Candidate[]; close: () => void }) {
  const dialogRef = useDialogFocus(close)
  const rows: Array<[string, (candidate: Candidate) => string]> = [
    ['Experience', c => `${c.total_experience} years`], ['Location', c => c.location || 'Not shared'],
    ['Current compensation', c => c.current_salary_lpa ? `₹${c.current_salary_lpa} LPA` : 'Not shared'],
    ['Expected salary', c => c.expected_salary_lpa ? `₹${c.expected_salary_lpa} LPA` : 'Not shared'],
    ['Notice period', c => c.notice_period_days == null ? 'Unknown' : `${c.notice_period_days} days`],
    ['Work preferences', c => c.work_preferences.join(', ') || 'Not added'],
    ['Employment type', c => c.employment_type || 'Not added'],
    ['Skills', c => c.skills.join(', ') || 'Not added'],
    ['Career history', c => c.work_experiences.map(item => `${item.role} · ${item.company}`).join('\n') || 'Not added'],
    ['Education', c => c.education.join('\n') || 'Not added'],
    ['Meaningful work', c => c.meaningful_work || 'Not added'],
  ]
  return <div ref={dialogRef as React.RefObject<HTMLDivElement>} tabIndex={-1} className="overlay recruiter-results-ui" role="dialog" aria-modal="true" aria-labelledby="candidate-comparison-title"><div className="compare-modal"><button className="close" aria-label="Close candidate comparison" onClick={close}><X /></button><div className="eyebrow">SIDE-BY-SIDE</div><h2 id="candidate-comparison-title">Candidate comparison</h2>
    <div className="compare-scroll" role="region" aria-label="Comparison details" tabIndex={0}><div className="compare-table" style={{ gridTemplateColumns: `150px repeat(${candidates.length}, minmax(190px, 1fr))` }}>
      <div /><>{candidates.map(c => <div className="compare-name" key={c.id}><b>{c.full_name}</b><span>{c.headline}</span></div>)}</>
      {rows.map(([label, value]) => <div className="compare-row" key={label} style={{ display: 'contents' }}><b>{label}</b>{candidates.map(c => <div key={c.id}>{value(c).split('\n').map(line => <span key={line}>{line}</span>)}</div>)}</div>)}
    </div></div>
  </div></div>
}

const emptyRecruiterFilters = {
  role: '', skills: '', location: '', min_experience: '', max_experience: '',
  notice_period_days: '', min_salary_lpa: '', max_salary_lpa: '',
  work_preferences: '', employment_type: '', stage: '',
}
const recruiterFilterLabels: Record<keyof typeof emptyRecruiterFilters, string> = {
  role: 'Role', skills: 'Skills', location: 'Location', min_experience: 'Min. years',
  max_experience: 'Max. years', notice_period_days: 'Max. notice (days)',
  min_salary_lpa: 'Min. LPA', max_salary_lpa: 'Max. LPA',
  work_preferences: 'Work setup', employment_type: 'Employment', stage: 'Stage',
}

function RecruiterPortal({ user, logout }: { user: User; logout: () => void }) {
  const [query, setQuery] = useState('')
  const [search, setSearch] = useState<Search | null>(null)
  const [recents, setRecents] = useState<Search[]>([])
  const [answer, setAnswer] = useState('')
  const [results, setResults] = useState<SearchResult[]>([])
  const [resultsLoaded, setResultsLoaded] = useState(false)
  const [selected, setSelected] = useState<number[]>([])
  const [profile, setProfile] = useState<Candidate | null>(null)
  const [comparison, setComparison] = useState<Candidate[]>([])
  const [notifications, setNotifications] = useState<Notification[]>([])
  const [projects, setProjects] = useState<Project[]>([])
  const [selectedProject, setSelectedProject] = useState<number | null>(null)
  const [projectDetail, setProjectDetail] = useState<ProjectDetail | null>(null)
  const [error, setError] = useState('')
  const [message, setMessage] = useState('')
  const [busy, setBusy] = useState(false)
  const [filters, setFilters] = useState(emptyRecruiterFilters)
  const [appliedFilters, setAppliedFilters] = useState(emptyRecruiterFilters)
  const [filterOpen, setFilterOpen] = useState(false)
  const filterPanelRef = useRef<HTMLElement>(null)
  useEffect(() => {
    const panel = filterPanelRef.current
    if (!filterOpen || !panel) return
    panel.querySelector<HTMLButtonElement>('button')?.focus()
    // Account for wrapped queries and active-filter chips above the panel.
    const fitPanel = () => {
      const top = Math.max(78, panel.getBoundingClientRect().top)
      panel.style.setProperty('--filter-available-height', `${Math.max(180, window.innerHeight - top - 16)}px`)
    }
    fitPanel()
    const observer = new ResizeObserver(fitPanel)
    const resultsView = panel.closest('.results-view')
    if (resultsView) observer.observe(resultsView)
    window.addEventListener('resize', fitPanel)
    window.addEventListener('scroll', fitPanel, { passive: true })
    return () => { observer.disconnect(); window.removeEventListener('resize', fitPanel); window.removeEventListener('scroll', fitPanel) }
  }, [filterOpen])
  function closeFilters() {
    setFilterOpen(false)
    document.querySelector<HTMLButtonElement>('.results-toolbar .filter-button')?.focus()
  }
  function filterPanelKeys(event: React.KeyboardEvent<HTMLElement>) {
    if (event.key === 'Escape') { event.preventDefault(); closeFilters(); return }
    if (event.key !== 'Tab' || !window.matchMedia('(max-width: 700px)').matches) return
    const controls = Array.from(event.currentTarget.querySelectorAll<HTMLElement>('button:not(:disabled), input, select'))
    const first = controls[0], last = controls[controls.length - 1]
    if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last?.focus() }
    else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first?.focus() }
  }
  const [workspacePanel, setWorkspacePanel] = useState<'recents' | 'projects' | 'updates' | null>(null)
  const [newProjectName, setNewProjectName] = useState('')
  const [voiceListening, setVoiceListening] = useState(false)
  const [nonRelevantCandidate, setNonRelevantCandidate] = useState<{ id: number; name: string } | null>(null)
  const [nonRelevantReasons, setNonRelevantReasons] = useState<string[]>([])
  const [nonRelevantNote, setNonRelevantNote] = useState('')
  const [savingFeedback, setSavingFeedback] = useState(false)
  useEffect(() => { Promise.all([api.searches(), api.notifications(), api.projects()]).then(([s, n, p]) => { setRecents(s); setNotifications(n); setProjects(p) }).catch(e => setError(e.message)) }, [])
  const activeProject = projects.find(item => item.id === selectedProject)
  const isSearchView = !projectDetail && !resultsLoaded

  async function refreshProjects(openId?: number) {
    const next = await api.projects()
    setProjects(next)
    if (openId) setProjectDetail(await api.project(openId))
  }
  async function createProject(event: FormEvent) {
    event.preventDefault()
    if (!newProjectName.trim()) return
    setBusy(true); setError('')
    try {
      const project = await api.createProject(newProjectName.trim())
      setNewProjectName(''); setSelectedProject(project.id)
      await refreshProjects()
    } catch (cause) { setError(cause instanceof Error ? cause.message : 'Could not create the project.') }
    finally { setBusy(false) }
  }
  function startVoiceSearch() {
    const speechWindow = window as typeof window & {
      SpeechRecognition?: SpeechRecognitionConstructor
      webkitSpeechRecognition?: SpeechRecognitionConstructor
    }
    const Recognition = speechWindow.SpeechRecognition || speechWindow.webkitSpeechRecognition
    if (!Recognition) {
      setError('Voice search is not supported in this browser. You can type your search instead.')
      return
    }
    const recognition = new Recognition()
    recognition.lang = 'en-IN'
    recognition.interimResults = false
    recognition.onresult = event => { setQuery(event.results[0][0].transcript); setError('') }
    recognition.onerror = () => setError('I could not hear that clearly. Please try again or type your search.')
    recognition.onend = () => setVoiceListening(false)
    setVoiceListening(true)
    recognition.start()
  }
  async function begin(event: FormEvent) {
    event.preventDefault(); setBusy(true); setError(''); setMessage(''); setResults([]); setResultsLoaded(false); setProjectDetail(null)
    try { const next = await api.createSearch(query, selectedProject || undefined); setSearch(next); setRecents(old => [next, ...old.filter(item => item.id !== next.id)]); if (next.state === 'complete') await loadResults(next.id) }
    catch (e) { setError(e instanceof Error ? e.message : 'Search failed.') } finally { setBusy(false) }
  }
  async function clarifyWith(value: string) {
    if (!search || !value.trim()) return; setBusy(true); setError(''); setMessage('')
    try { const next = await api.answerSearch(search.id, value); setSearch(next); setAnswer(''); setRecents(old => old.map(item => item.id === next.id ? next : item)); if (next.state === 'complete') await loadResults(next.id) }
    catch (e) { setError(e instanceof Error ? e.message : 'Could not continue.') } finally { setBusy(false) }
  }
  async function loadResults(id = search?.id, nextFilters = filters) {
    if (!id) return
    const params = new URLSearchParams(Object.entries(nextFilters).filter(([, value]) => value)).toString()
    try { const payload = await api.results(id, params ? `?${params}` : ''); setSearch(payload.search); setResults(payload.results); setAppliedFilters({ ...nextFilters }); setResultsLoaded(true); setProjectDetail(null) }
    catch (cause) { setError(cause instanceof Error ? cause.message : 'Could not load candidates.') }
  }
  async function openProfile(id: number) { try { const item = await api.candidate(id); setProfile(item); setResults(old => old.map(row => row.candidate.id === id ? { ...row, candidate: { ...row.candidate, viewed: true } } : row)) } catch (e) { setError(e instanceof Error ? e.message : 'Could not open profile.') } }
  async function persistStatus(id: number, value: string, reason = '', note = '') { try { if (value) await api.setStatus(id, value, reason, note); else await api.clearStatus(id); setResults(old => old.map(row => row.candidate.id === id ? { ...row, candidate: { ...row.candidate, stage: value } } : row)); if (profile?.id === id) setProfile({ ...profile, stage: value }) } catch (e) { setError(e instanceof Error ? e.message : 'Status failed.'); throw e } }
  function setStatus(id: number, name: string, value: string) {
    if (value === 'non_relevant') {
      setNonRelevantCandidate({ id, name }); setNonRelevantReasons([]); setNonRelevantNote(''); return
    }
    void persistStatus(id, value)
  }
  function toggleNonRelevantReason(reason: string) { setNonRelevantReasons(old => old.includes(reason) ? old.filter(item => item !== reason) : [...old, reason]) }
  async function saveNonRelevant(event: FormEvent) {
    event.preventDefault()
    if (!nonRelevantCandidate || (nonRelevantReasons.length === 0 && !nonRelevantNote.trim())) return
    setSavingFeedback(true)
    try {
      await persistStatus(nonRelevantCandidate.id, 'non_relevant', nonRelevantReasons.join(', '), nonRelevantNote.trim())
      setNonRelevantCandidate(null); setNonRelevantReasons([]); setNonRelevantNote('')
    } catch { /* persistStatus presents the error */ } finally { setSavingFeedback(false) }
  }
  async function compare() { try { setComparison(await api.compare(selected)) } catch (e) { setError(e instanceof Error ? e.message : 'Comparison failed.') } }
  function chooseRecent(item: Search) { setSearch(item); setQuery(item.query); setAnswer(''); setResults([]); setResultsLoaded(false); setProjectDetail(null); setSelectedProject(item.project); setWorkspacePanel(null); if (item.state === 'complete') loadResults(item.id) }
  async function openProject(id: number) { setError(''); setSelectedProject(id); setWorkspacePanel(null); setResultsLoaded(false); setSearch(null); try { setProjectDetail(await api.project(id)) } catch (cause) { setError(cause instanceof Error ? cause.message : 'Could not open project.') } }
  async function addToProject(projectId: number, candidateId: number) { try { await api.addCandidateToProject(projectId, candidateId); await refreshProjects(projectDetail?.project.id === projectId ? projectId : undefined); setMessage(`Candidate saved to ${projects.find(item => item.id === projectId)?.name || 'project'}.`) } catch (cause) { setError(cause instanceof Error ? cause.message : 'Could not save candidate.') } }
  async function removeFromProject(candidateId: number) { if (!projectDetail) return; try { await api.removeCandidateFromProject(projectDetail.project.id, candidateId); await refreshProjects(projectDetail.project.id); setMessage('Candidate removed from the project.') } catch (cause) { setError(cause instanceof Error ? cause.message : 'Could not remove candidate.') } }
  async function openNotification(item: Notification) { try { if (!item.is_read) { await api.markNotificationRead(item.id); setNotifications(old => old.map(value => value.id === item.id ? { ...value, is_read: true } : value)) } await openProfile(item.candidate); setWorkspacePanel(null) } catch (cause) { setError(cause instanceof Error ? cause.message : 'Could not open candidate update.') } }
  function toggleWorkspacePanel(panel: 'recents' | 'projects' | 'updates') {
    setFilterOpen(false)
    setWorkspacePanel(current => current === panel ? null : panel)
  }
  function applyQuickStage(stage: string) {
    const nextFilters = { ...filters, stage }
    setFilters(nextFilters)
    loadResults(search?.id, nextFilters)
  }
  return <Shell user={user} logout={logout} noticeCount={notifications.filter(n => !n.is_read).length}>
    <main className={`recruiter-page ${isSearchView ? 'recruiter-search-mode' : ''} ${projectDetail ? 'project-workspace-mode' : ''} ${workspacePanel ? 'workspace-panel-open' : ''}`}>
      <nav className="recruiter-rail" aria-label="Recruiter workspace">
        <button className="rail-new-search" title="New search" aria-label="New search" onClick={() => { setSearch(null); setProjectDetail(null); setQuery(''); setResults([]); setResultsLoaded(false); setSelected([]); setWorkspacePanel(null) }}><Plus />{isSearchView && <small className="rail-label">New search</small>}</button>
        <button className={workspacePanel === 'recents' ? 'active' : ''} title="Recent searches" aria-label="Recent searches" aria-expanded={workspacePanel === 'recents'} onClick={() => toggleWorkspacePanel('recents')}><History />{isSearchView && <small className="rail-label">Recents</small>}</button>
        <button className={workspacePanel === 'projects' || (projectDetail && !workspacePanel) ? 'active' : ''} title="Projects" aria-label="Projects" aria-current={projectDetail && !workspacePanel ? 'page' : undefined} aria-expanded={workspacePanel === 'projects'} onClick={() => toggleWorkspacePanel('projects')}><BriefcaseBusiness />{isSearchView && <small className="rail-label">Projects</small>}</button>
        <button className={workspacePanel === 'updates' ? 'active' : ''} title="Candidate updates" aria-label="Candidate updates" aria-expanded={workspacePanel === 'updates'} onClick={() => toggleWorkspacePanel('updates')}><Bell />{isSearchView && <small className="rail-label">Updates</small>}{notifications.some(item => !item.is_read) && <span>{notifications.filter(item => !item.is_read).length}</span>}</button>
      </nav>
      <section className="recruiter-content">
        {message && <div className="recruiter-toast"><Check size={16} />{message}<button onClick={() => setMessage('')}><X size={14} /></button></div>}
        {projectDetail ? <ProjectWorkspace detail={projectDetail} error={error} stageLabel={recruiterStageLabel} openCandidate={openProfile} removeCandidate={removeFromProject} openSearch={chooseRecent} startSearch={() => { setProjectDetail(null); setQuery(''); setSearch(null) }} /> : !resultsLoaded && <RecruiterSearch
          query={query} setQuery={setQuery} search={search} answer={answer} setAnswer={setAnswer}
          submit={begin} clarify={clarifyWith} busy={busy} error={error}
          projectName={activeProject?.name} clearProject={() => setSelectedProject(null)}
          voiceListening={voiceListening} startVoiceSearch={startVoiceSearch}
        />}
        {resultsLoaded && <div className="results-view recruiter-results-ui">
          <div className="results-head results-toolbar"><div><h1>Showing {results.length} of {results.length} results</h1><p>{search?.query}{search?.project_name && ` · ${search.project_name}`}</p></div><div className="results-toolbar-actions"><button className="header-compare" aria-label="Compare" disabled={selected.length < 2} onClick={compare}>Compare ({selected.length})</button><select aria-label="Quick result filter" value={filters.stage} onChange={event => applyQuickStage(event.target.value)}><option value="">All stages</option><option value="unviewed">Not viewed</option><option value="viewed">Viewed</option>{recruiterStages.map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select><button className={`filter-button ${filterOpen ? 'active' : ''}`} onClick={() => { setWorkspacePanel(null); setFilterOpen(value => !value) }} aria-expanded={filterOpen} aria-label={filterOpen ? 'Hide filters' : 'Refine'} title={filterOpen ? 'Hide filters' : 'Refine'}><SlidersHorizontal /></button></div></div>
          {Object.values(appliedFilters).some(Boolean) && <div className="applied-result-filters" aria-label="Applied filters"><b>Applied filters</b>{Object.entries(appliedFilters).filter(([, value]) => value).map(([key, value]) => <span key={key}>{recruiterFilterLabels[key as keyof typeof emptyRecruiterFilters]}: {key === 'stage' ? ({ viewed: 'Viewed', unviewed: 'Not viewed' }[value] || recruiterStageLabel(value)) : value}</span>)}</div>}
          <div className={`results-layout ${filterOpen ? 'refine-open' : ''}`}>
          <div className="results-column">
          <InlineError value={error} />
          {results.length === 0 ? <div className="empty-results"><SearchIcon size={28} /><h2>No candidates match these filters</h2><p>Broaden the role, skills, location, experience, notice, compensation, or preference criteria.</p><button className="primary small" onClick={() => { setFilters(emptyRecruiterFilters); loadResults(search?.id, emptyRecruiterFilters) }}>Clear filters</button></div> : <div className="candidate-list">{results.map(result => <CandidateCard key={result.candidate.id} result={result} selected={selected.includes(result.candidate.id)} toggle={() => setSelected(old => old.includes(result.candidate.id) ? old.filter(id => id !== result.candidate.id) : old.length < 4 ? [...old, result.candidate.id] : old)} open={() => openProfile(result.candidate.id)} status={value => setStatus(result.candidate.id, result.candidate.full_name, value)} />)}</div>}
          </div>
          {filterOpen && <aside ref={filterPanelRef} className="results-filter-panel" aria-label="Refine candidate results" onKeyDown={filterPanelKeys}><div className="filter-panel-head"><div><span>REFINE</span><h2>Shape the shortlist</h2></div><button aria-label="Close filters" title="Close filters" onClick={closeFilters}><X /></button></div><form id="recruiter-result-filters" className="filter-bar expanded" onSubmit={e => { e.preventDefault(); loadResults() }}>
            <fieldset><legend>Role &amp; expertise</legend>
            <label>Role<input value={filters.role} onChange={e => setFilters({ ...filters, role: e.target.value })} placeholder="Backend engineer" /></label>
            <label>Skills<input value={filters.skills} onChange={e => setFilters({ ...filters, skills: e.target.value })} placeholder="Python, Django" /></label>
            <div className="filter-pair">
            <label>Min. experience<input type="number" min="0" value={filters.min_experience} onChange={e => setFilters({ ...filters, min_experience: e.target.value })} placeholder="Years" /></label>
            <label>Max. experience<input type="number" min="0" value={filters.max_experience} onChange={e => setFilters({ ...filters, max_experience: e.target.value })} placeholder="Years" /></label>
            </div></fieldset>
            <fieldset><legend>Location &amp; availability</legend>
            <label>Location<input value={filters.location} onChange={e => setFilters({ ...filters, location: e.target.value })} placeholder="Any location" /></label>
            <label>Max. notice<input type="number" min="0" value={filters.notice_period_days} onChange={e => setFilters({ ...filters, notice_period_days: e.target.value })} placeholder="Days" /></label>
            </fieldset><fieldset><legend>Compensation</legend><div className="filter-pair">
            <label>Min. compensation<input type="number" min="0" value={filters.min_salary_lpa} onChange={e => setFilters({ ...filters, min_salary_lpa: e.target.value })} placeholder="LPA" /></label>
            <label>Max. compensation<input type="number" min="0" value={filters.max_salary_lpa} onChange={e => setFilters({ ...filters, max_salary_lpa: e.target.value })} placeholder="LPA" /></label>
            </div></fieldset><fieldset><legend>Opportunity &amp; pipeline</legend>
            <label>Work preference<select value={filters.work_preferences} onChange={e => setFilters({ ...filters, work_preferences: e.target.value })}><option value="">Any setup</option><option>Flexible</option><option>Remote</option><option>Hybrid</option><option>On-site</option></select></label>
            <label>Employment type<select value={filters.employment_type} onChange={e => setFilters({ ...filters, employment_type: e.target.value })}><option value="">Any type</option><option>Full-time</option><option>Contract</option><option>Part-time</option></select></label>
            <label>Recruiting stage<select value={filters.stage} onChange={e => setFilters({ ...filters, stage: e.target.value })}><option value="">Any stage</option><option value="unviewed">Not viewed</option><option value="viewed">Viewed</option>{recruiterStages.map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></label>
            </fieldset>
          </form><div className="filter-actions"><button type="button" onClick={() => { setFilters(emptyRecruiterFilters); loadResults(search?.id, emptyRecruiterFilters) }}>Clear</button><button className="primary" form="recruiter-result-filters" type="submit">Apply filters</button></div></aside>}
          </div>
        </div>}
      </section>
      {workspacePanel && <WorkspacePanel panel={workspacePanel} close={() => setWorkspacePanel(null)} recents={recents} projects={projects} notifications={notifications} selectedProject={selectedProject} newProjectName={newProjectName} setNewProjectName={setNewProjectName} createProject={createProject} busy={busy} chooseRecent={chooseRecent} openProject={openProject} openNotification={openNotification} error={error} />}
      {profile && <ProfileDrawer candidate={profile} close={() => setProfile(null)} refresh={() => openProfile(profile.id)} projects={projects} selectedProject={selectedProject} addToProject={addToProject} />}
      {nonRelevantCandidate && <NonRelevantDialog candidateName={nonRelevantCandidate.name} reasons={nonRelevantReasons} note={nonRelevantNote} saving={savingFeedback} toggleReason={toggleNonRelevantReason} setNote={setNonRelevantNote} cancel={() => setNonRelevantCandidate(null)} save={saveNonRelevant} />}
      {comparison.length > 0 && <CompareModal candidates={comparison} close={() => setComparison([])} />}
    </main>
  </Shell>
}

export default function App() {
  const [user, setUser] = useState<User | null | undefined>(undefined)
  const [choice, setChoice] = useState<'candidate' | 'recruiter' | null>(null)
  const [authMode, setAuthMode] = useState<'signup' | 'login'>('signup')
  const [accountRemoved, setAccountRemoved] = useState(false)
  const screen = useMemo(() => user?.role || choice, [user, choice])
  useEffect(() => {
    api.me().then(setUser).catch(() => setUser(null))
  }, [])
  useEffect(() => {
    const expireSession = () => {
      auth.clear()
      setUser(null)
      setChoice(null)
    }
    window.addEventListener('enter-auth-expired', expireSession)
    return () => window.removeEventListener('enter-auth-expired', expireSession)
  }, [])
  async function logout() { try { await api.logout() } catch { /* local logout still applies */ } auth.clear(); setUser(null); setChoice(null) }
  const path = window.location.pathname
  const query = new URLSearchParams(window.location.search)
  if (path === '/privacy') return <LegalPlaceholder kind="privacy" />
  if (path === '/terms') return <LegalPlaceholder kind="terms" />
  const verificationToken = query.get('verify-email')
  if (verificationToken) return <EmailVerificationScreen token={verificationToken} onDone={payload => setUser(payload.user)} />
  const resetToken = query.get('reset-password')
  if (resetToken) return <PasswordResetScreen token={resetToken} done={() => { setAuthMode('login'); setChoice('candidate'); setUser(null) }} />
  if (user === undefined) return <main className="auth-page"><div className="candidate-profile-loading" role="status">Opening Enter…</div></main>
  if (accountRemoved) return <main className="auth-page"><section className="auth-card auth-state-card"><Brand /><div className="auth-state-icon"><CheckCircle2 /></div><h1>Your account has been deleted</h1><p>Your candidate profile and stored resumes were permanently removed.</p><button className="primary" onClick={() => { setAccountRemoved(false); setChoice(null) }}>Return to Enter</button></section></main>
  if (!screen) return <Landing choose={(role, mode = 'signup') => { setAuthMode(mode); setChoice(role) }} />
  if (!user) return <AuthScreen role={screen} initialMode={authMode} back={() => setChoice(null)} onDone={payload => setUser(payload.user)} />
  return user.role === 'candidate' ? <CandidatePortal user={user} logout={logout} accountDeleted={() => { setUser(null); setChoice(null); setAccountRemoved(true) }} /> : <RecruiterPortal user={user} logout={logout} />
}
