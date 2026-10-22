import { FormEvent, useEffect, useMemo, useRef, useState } from 'react'
import {
  Bell, BriefcaseBusiness, CalendarDays, Check,
  CheckCircle2, FolderPlus, GraduationCap,
  History, IndianRupee, LogOut, Mail, MapPin, MessageCircle, Plus,
  Search as SearchIcon, ShieldCheck, SlidersHorizontal, X, ChevronDown,
} from 'lucide-react'
import { api, ApiError, auth } from './api'
import type { AuthPayload } from './api'
import type { Candidate, Notification, Project, ProjectDetail, Search, SearchResult, User } from './types'
import { Badge, Button, Card, FormField } from './components/ui'
import Landing from './components/Landing'
import PlatformBackground from './components/PlatformBackground'
import RecruiterSearch from './components/RecruiterSearch'
import ResumeAccess from './components/ResumeAccess'
import { GithubMark, LinkedInMark } from './components/ProfileMarks'
import { ProjectWorkspace, WorkspacePanel } from './components/RecruiterWorkspace'
import CandidateExperience from './components/CandidateExperience'
import CareerJourney from './components/CareerJourney'
import './components/auth.css'
import EnterBrandText from './components/EnterBrandText'
import './components/onboarding.css'
import { LegalChecks, LegalRetry, UnpublishedLegalPage } from './components/LegalReview'
import { legalWorkflow, useLegalDocumentState } from './legalReview'

type SpeechRecognitionLike = {
  lang: string
  interimResults: boolean
  start: () => void
  onresult: ((event: { results: { 0: { 0: { transcript: string } } } }) => void) | null
  onerror: (() => void) | null
  onend: (() => void) | null
}
type SpeechRecognitionConstructor = new () => SpeechRecognitionLike

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


function AuthLayout({ role, back, children, onboardingMode }: {
  onboardingMode?: 'signup' | 'login'
  role?: 'candidate' | 'recruiter'
  back?: () => void
  children: React.ReactNode
}) {
  const candidate = role === 'candidate'
  return <main className={`auth-page auth-editorial ${candidate ? 'candidate-theme' : ''} ${candidate && onboardingMode ? 'candidate-onboarding-auth' : ''}`}>
    <header className="auth-masthead">
      <Brand />
      {back ? <Button variant="ghost" size="small" onClick={back}>{candidate && onboardingMode ? <EnterBrandText text="← Back to ENTER" /> : '← Back to Enter'}</Button> : <a href="/">← Back to Enter</a>}
    </header>
    <div className="auth-layout">
      <aside className="auth-story">
        <div className="auth-story__copy">
          <span className="auth-context-label">{role ? candidate ? 'FOR CANDIDATES' : 'FOR RECRUITERS' : 'YOUR ENTER ACCOUNT'}</span>
          <h2>{candidate && onboardingMode ? <EnterBrandText text="Join Leading Startups Building Their Teams with ENTER" /> : role ? candidate ? 'Your work. Your story.' : 'Good hiring starts with understanding.' : 'A simple way back to what’s next.'}</h2>
          <p>{!role ? 'Manage access to your Enter account and pick up where you left off.' : candidate
            ? onboardingMode === 'signup' ? <EnterBrandText text="Your experience deserves to be understood. Create your profile and let ENTER find opportunities that fit." /> : onboardingMode === 'login' ? 'Welcome back. Your next opportunity could be closer than you think.' : 'Turn your resume into a profile you control, then decide how the right recruiters can find you.'
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
  const { documents: legalDocuments, loading: legalLoading, error: legalError } = useLegalDocumentState()
  const [mode, setMode] = useState<'signup' | 'login' | 'forgot'>(role === 'recruiter' ? 'login' : initialMode)
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
        ? await api.signup({ ...data, role, age_accepted: data.age_accepted === 'on', terms_accepted: data.terms_accepted === 'on' })
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
      if (role === 'candidate' && mode === 'login' && err instanceof ApiError && err.code === 'email_not_verified') {
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
  return <AuthLayout role={role} back={back} onboardingMode={mode === 'forgot' ? undefined : mode}>
    <Card className="auth-card">
      <form className="auth-form" onSubmit={submit}>
        <Badge tone="neutral">{role === 'recruiter' ? 'RECRUITER WORKSPACE' : 'CANDIDATE PROFILE'}</Badge>
        <h1>{mode === 'signup' ? 'Create your account' : mode === 'forgot' ? 'Forgot your password?' : 'Welcome back'}</h1>
        <p>{mode === 'forgot' ? 'Enter your email. If an account exists, we’ll send a secure reset link.' : role === 'recruiter' ? 'Search real candidate profiles and build a thoughtful shortlist.' : 'Turn your resume into a profile you control.'}</p>
        <div className="auth-fields">
          {mode === 'signup' && <FormField label="Full name" name="full_name" required autoComplete="name" />}
          {mode === 'signup' && <label className="auth-country-field"><span>Country</span><select name="country_code" defaultValue="IN" required><option value="IN">India</option></select><small>Candidate registration is currently available in India.</small></label>}
          <FormField label="Email" name="email" type="email" required autoComplete="email" />
          {mode !== 'forgot' && <FormField label="Password" name="password" type="password" minLength={8} required autoComplete={mode === 'signup' ? 'new-password' : 'current-password'} hint={mode === 'signup' ? 'Use at least 8 characters.' : undefined} />}
        </div>
        <InlineError value={error} />
        {message && <div className="success" role="status"><Check size={17} aria-hidden="true" />{message}</div>}
        {mode === 'signup' && legalWorkflow && (legalDocuments ? <LegalChecks key={legalDocuments.terms.version} documents={legalDocuments} /> : <div role={legalError ? 'alert' : 'status'}>{legalLoading ? 'Loading legal documents…' : legalError || 'Legal documents unavailable. Registration is disabled.'}<LegalRetry /></div>)}
        {mode === 'signup' && legalWorkflow && legalDocuments && <LegalRetry />}
        {mode === 'signup' && <p><a href="/privacy" target="_blank" rel="noopener noreferrer">Privacy Policy</a> · <a href="/terms" target="_blank" rel="noopener noreferrer">Terms of Use</a></p>}
        <Button size="large" fullWidth disabled={busy || (mode === 'signup' && legalWorkflow && !legalDocuments)}>{busy ? 'Please wait…' : mode === 'signup' ? 'Create account' : mode === 'forgot' ? 'Send reset link' : 'Log in'}</Button>
        {mode === 'login' && <Button type="button" variant="ghost" fullWidth onClick={() => { setMode('forgot'); setError(''); setMessage('') }}>Forgot password?</Button>}
        {(role === 'candidate' || mode === 'forgot') && <Button type="button" variant="ghost" fullWidth onClick={() => { setMode(mode === 'signup' ? 'login' : mode === 'login' ? 'signup' : 'login'); setError(''); setMessage('') }}>
          {mode === 'signup' ? 'Already have an account? Log in' : mode === 'login' ? 'New here? Create an account' : 'Back to login'}
        </Button>}
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

function PasswordResetScreen({ token, done }: { token: string; done: (role: 'candidate' | 'recruiter') => void }) {
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [complete, setComplete] = useState(false)
  const [accountRole, setAccountRole] = useState<'candidate' | 'recruiter'>('candidate')
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); setBusy(true); setError('')
    const data = Object.fromEntries(new FormData(event.currentTarget).entries()) as Record<string, string>
    if (data.password !== data.confirm_password) { setError('Passwords do not match.'); setBusy(false); return }
    try { const response = await api.confirmPasswordReset(token, data.password); setAccountRole(response.role === 'recruiter' ? 'recruiter' : 'candidate'); setComplete(true); window.history.replaceState({}, '', '/') }
    catch (cause) { setError(cause instanceof Error ? cause.message : 'This reset link could not be used.') }
    finally { setBusy(false) }
  }
  return <AuthLayout><Card className="auth-card auth-state-card">
    <div className="auth-state-icon"><ShieldCheck aria-hidden="true" /></div>
    <h1>{complete ? 'Password updated' : 'Choose a new password'}</h1>
    {complete ? <><p role="status">Your password has been changed and existing sessions have been signed out.</p><Button fullWidth onClick={() => done(accountRole)}>Continue to login</Button></>
      : <form className="nested-auth-form" onSubmit={submit}><p>Use a strong password you don’t use elsewhere.</p><FormField label="New password" name="password" type="password" minLength={8} required autoComplete="new-password" /><FormField label="Confirm password" name="confirm_password" type="password" minLength={8} required autoComplete="new-password" /><InlineError value={error} /><Button fullWidth disabled={busy}>{busy ? 'Updating…' : 'Reset password'}</Button></form>}
  </Card></AuthLayout>
}

function LegalPlaceholder({ kind }: { kind: 'privacy' | 'terms' }) {
  if (legalWorkflow) return <UnpublishedLegalPage kind={kind} />
  const title = kind === 'privacy' ? 'Privacy Policy' : 'Terms'
  return <main className="legal-page"><nav><Brand /><a href="/">Back to Enter</a></nav><article>
    <span>LEGAL REVIEW REQUIRED</span><h1>{title} placeholder</h1>
    <p>This page is intentionally a placeholder. It is not a legal policy and must be replaced with counsel-reviewed {title.toLowerCase()} before public launch.</p>
    <div><ShieldCheck /><p>Enter’s implemented product controls currently include private resume delivery, candidate-controlled visibility, backend authorization, account deletion, email verification, and recorded submission consent.</p></div>
  </article></main>
}

function Shell({ user, logout, children, noticeCount = 0, accountMenu }: {
  user: User; logout: () => void; children: React.ReactNode; noticeCount?: number; accountMenu?: React.ReactNode
}) {
  return <div className="app-shell">
    <header><Brand compact /><div className="header-user">
      {user.role === 'recruiter' && <span className="notification-pill"><Bell size={15} /> {noticeCount}</span>}
      {accountMenu || <span>{user.full_name}</span>}<button onClick={logout} aria-label="Log out"><LogOut size={17} /></button>
    </div></header>
    {children}
  </div>
}

function CandidateAccountMenu({ user, accountDeleted }: { user: User; accountDeleted: () => void }) {
  const [open, setOpen] = useState(false)
  const [deleting, setDeleting] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  return <div className="candidate-account-menu"><button type="button" className="candidate-account-trigger" aria-expanded={open} aria-controls="candidate-account-popover" onClick={() => setOpen(value => !value)}>{user.full_name}<ChevronDown size={15} aria-hidden="true" /></button>{open && <section id="candidate-account-popover" className="candidate-account-popover" aria-label="Account menu"><strong>Account</strong><p>Manage your ENTER profile and account.</p>{error && <p role="alert" className="error">{error}</p>}{!deleting ? <button type="button" className="cp-danger" onClick={() => setDeleting(true)}>Delete my account</button> : <form onSubmit={async event => { event.preventDefault(); const data = new FormData(event.currentTarget); setBusy(true); setError(''); try { await api.deleteCandidateAccount(String(data.get('password')), String(data.get('confirmation'))); accountDeleted() } catch (cause) { setError(cause instanceof Error ? cause.message : 'Could not delete account.') } finally { setBusy(false) } }}><label>Current password<input type="password" name="password" autoComplete="current-password" required /></label><label>Type DELETE to confirm<input name="confirmation" required pattern="DELETE" /></label><div><button disabled={busy} className="cp-danger">Permanently delete my account</button><button type="button" disabled={busy} onClick={() => { setDeleting(false); setError('') }}>Cancel</button></div></form>}</section>}</div>
}

function CandidatePortal({ user, logout, accountDeleted }: { user: User; logout: () => void; accountDeleted: () => void }) {
  const beforeLeave = useRef<(() => Promise<boolean>) | null>(null)
  return <Shell user={user} accountMenu={<CandidateAccountMenu user={user} accountDeleted={accountDeleted} />} logout={() => { void (async () => { if (!beforeLeave.current || await beforeLeave.current()) logout() })() }}><CandidateExperience beforeLeaveRef={beforeLeave} /></Shell>
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
  work_preferences: 'Work mode', employment_type: 'Employment', stage: 'Stage',
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
    panel.querySelector<HTMLButtonElement>('button')?.focus({ preventScroll: true })
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
  const [path, setPath] = useState(window.location.pathname)
  const [user, setUser] = useState<User | null | undefined>(undefined)
  const [choice, setChoice] = useState<'candidate' | 'recruiter' | null>(null)
  const [authMode, setAuthMode] = useState<'signup' | 'login'>('signup')
  const [accountRemoved, setAccountRemoved] = useState(false)
  const screen = useMemo(() => user?.role || choice || (path === '/recruiter' || path === '/recruiter/account' ? 'recruiter' : null), [user, choice, path])
  function navigate(next: string) {
    window.history.pushState({}, '', next)
    setPath(next); setChoice(null)
    window.scrollTo(0, 0)
  }
  useEffect(() => {
    const onBack = () => { setPath(window.location.pathname); setChoice(null) }
    window.addEventListener('popstate', onBack)
    return () => window.removeEventListener('popstate', onBack)
  }, [])
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
  async function logout() { try { await api.logout() } catch { /* local logout still applies */ } auth.clear(); setUser(null); navigate('/') }
  const query = new URLSearchParams(window.location.search)
  if (import.meta.env.VITE_CANDIDATE_ONLY === 'true' && (path.startsWith('/recruiter') || screen === 'recruiter')) return <PlatformBackground><main className="auth-page"><section className="auth-card"><h1>This platform is not available</h1><button onClick={() => { setUser(null); navigate('/') }}>Return to Enter</button></section></main></PlatformBackground>
  if (path === '/privacy') return <LegalPlaceholder kind="privacy" />
  if (path === '/terms') return <LegalPlaceholder kind="terms" />
  const verificationToken = query.get('verify-email')
  if (verificationToken) return <PlatformBackground>{<EmailVerificationScreen token={verificationToken} onDone={payload => setUser(payload.user)} />}</PlatformBackground>
  const resetToken = query.get('reset-password')
  if (resetToken) return <PlatformBackground>{<PasswordResetScreen token={resetToken} done={role => { setAuthMode('login'); if (role === 'recruiter') navigate('/recruiter'); else setChoice('candidate'); setUser(null) }} />}</PlatformBackground>
  if (user === undefined) return <PlatformBackground>{<main className="auth-page"><div className="candidate-profile-loading" role="status">Opening Enter…</div></main>}</PlatformBackground>
  if (accountRemoved) return <PlatformBackground>{<main className="auth-page"><section className="auth-card auth-state-card"><Brand /><div className="auth-state-icon"><CheckCircle2 /></div><h1>Your account has been deleted</h1><p>Your profile is no longer accessible. Private file cleanup has been scheduled securely.</p><button className="primary" onClick={() => { setAccountRemoved(false); setChoice(null) }}>Return to Enter</button></section></main>}</PlatformBackground>
  if (!screen) return <Landing choose={(role, mode = 'signup') => { if (role === 'recruiter') navigate('/recruiter'); else { setAuthMode(mode); setChoice(role) } }} />
  if (!user) return <PlatformBackground>{<AuthScreen role={screen} initialMode={authMode} back={() => navigate('/')} onDone={payload => setUser(payload.user)} />}</PlatformBackground>
  return <PlatformBackground>{user.role === 'candidate' ? <CandidatePortal user={user} logout={logout} accountDeleted={() => { setUser(null); setChoice(null); setAccountRemoved(true) }} /> : <RecruiterPortal user={user} logout={logout} />}</PlatformBackground>
}
