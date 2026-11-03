import { applicationProfileReady } from '../opportunityApplication'
import { useEffect, useRef, useState } from 'react'
import { api } from '../api'
import type { Candidate } from '../types'
import CandidateExperience from './CandidateExperience'
import PlatformBackground from './PlatformBackground'
import EnterLogo from './EnterLogo'
import './opportunity-application.css'


export default function OpportunityApplication({ role, onBack }: {
  role: { id: string; title: string }; onBack: () => void
}) {
  const [step, setStep] = useState<'cv' | 'profile' | 'confirm' | 'success'>('cv')
  const [profile, setProfile] = useState<Candidate | null>(null)
  const [error, setError] = useState('')
  const [attempt, setAttempt] = useState(0)
  const [note, setNote] = useState('')
  const [confirmed, setConfirmed] = useState(false)
  const [busy, setBusy] = useState(false)
  const [message, setMessage] = useState('')
  const beforeLeave = useRef<(() => Promise<boolean>) | null>(null)
  const heading = useRef<HTMLHeadingElement>(null)
  useEffect(() => {
    let active = true
    api.candidateProfile().then(value => { if (active) { setProfile(value); setError('') } })
      .catch(cause => { if (active) setError(cause instanceof Error ? cause.message : 'Could not open your profile.') })
    return () => { active = false }
  }, [attempt])
  useEffect(() => { heading.current?.focus(); window.scrollTo(0, 0) }, [step])
  async function back() {
    if (busy || (beforeLeave.current && !await beforeLeave.current())) return
    onBack()
  }
  async function upload(file?: File) {
    if (!file || busy) return
    if (!/\.(pdf|docx)$/i.test(file.name) || file.size > 5 * 1024 * 1024) {
      setError('Choose a PDF or DOCX, up to 5 MB.'); return
    }
    setBusy(true); setError('')
    try { setProfile(await api.uploadResume(file)); setStep('profile') }
    catch (cause) { setError(cause instanceof Error ? cause.message : 'Could not upload your CV. Please try again.') }
    finally { setBusy(false) }
  }
  async function submit(event: React.FormEvent) {
    event.preventDefault()
    if (busy || !confirmed || !profile) return
    setBusy(true); setError('')
    try {
      const current = await api.candidateProfile()
      if (!applicationProfileReady(current) || current.latest_resume?.id !== profile.latest_resume?.id || current.profile_updated_at !== profile.profile_updated_at) {
        setProfile(current); setConfirmed(false); setStep('profile')
        setError('Your CV or profile has changed. Please review it again before applying.')
        return
      }
      const result = await api.applyOpportunity(role.id, note)
      setMessage(result.detail); setStep('success')
      sessionStorage.removeItem('enter-opportunity-intent')
    } catch (cause) { setError(cause instanceof Error ? cause.message : 'Could not submit. Please try again.') }
    finally { setBusy(false) }
  }
  return <PlatformBackground><div className="opportunity-application-page">
    <header className="opp-header"><a href="/" aria-label="Enter home"><EnterLogo /></a><button type="button" disabled={busy} onClick={() => void back()}>Back to opportunities</button></header>
    <section className="opp-application-shell">
      <p className="opp-eyebrow">{step === 'success' ? 'APPLICATION RECEIVED' : 'YOUR APPLICATION'}</p>
      <h1 ref={heading} tabIndex={-1}>{role.title}</h1>
      {step !== 'success' && <ol className="opp-application-steps" aria-label="Application progress">{['Choose CV', 'Review profile', 'Submit application'].map((label, index) => <li key={label} aria-current={index === ['cv', 'profile', 'confirm'].indexOf(step) ? 'step' : undefined}>{index + 1}. {label}</li>)}</ol>}
      {error && <p role="alert" className="error">{error}</p>}
      {step === 'cv' && (!profile ? <><p role="status">{error ? 'Your profile could not be loaded.' : 'Opening your profile…'}</p>{error && <button onClick={() => { setError(''); setAttempt(value => value + 1) }}>Try again</button>}</> : <>
        <h2>{profile.latest_resume ? 'Choose your CV' : 'Start with your CV'}</h2>
        <p>{profile.latest_resume ? `Current CV: ${profile.latest_resume.original_name}` : 'Upload your CV, then review the profile details extracted from it.'}</p>
        <p>PDF or DOCX, up to 5 MB. Your CV stays private and you can review your profile before applying.</p>
        <div className="cp-actions">{profile.latest_resume?.processing_status === 'completed' && profile.latest_resume.scan_status === 'clean' && !profile.resume_identity_warning && <button className="primary" onClick={() => setStep('profile')}>Use current CV</button>}<label className="opp-cv-upload">{busy ? 'Uploading…' : profile.latest_resume ? 'Upload updated CV' : 'Upload your CV'}<input aria-label={profile.latest_resume ? 'Upload updated CV' : 'Upload your CV'} type="file" accept=".pdf,.docx" disabled={busy} onChange={event => { void upload(event.target.files?.[0]); event.target.value = '' }} /></label></div>
      </>)}
      {step === 'confirm' && profile && <form onSubmit={event => void submit(event)} className="opp-application">
        <h2>Review your application</h2><p><strong>{profile.full_name}</strong>{profile.location && ` · ${profile.location}`}</p><p>CV: {profile.latest_resume?.original_name}</p>
        <button type="button" disabled={busy} onClick={() => { setConfirmed(false); setStep('profile') }}>Edit CV or profile</button>
        <label>Anything you’d like us to know? (optional)<textarea value={note} onChange={event => setNote(event.target.value)} maxLength={5000} rows={5} disabled={busy} /></label>
        <label className="cp-check"><input type="checkbox" checked={confirmed} onChange={event => setConfirmed(event.target.checked)} disabled={busy} required />I have reviewed my CV and profile and want to apply for {role.title}.</label>
        <p>This application is linked to your saved candidate profile. It does not change your recruiter sharing preferences.</p>
        <button className="primary" disabled={busy || !confirmed}>{busy ? 'Submitting…' : 'Submit application'}</button>
      </form>}
      {step === 'success' && <div role="status"><h2>{message}</h2><p>Role: {role.title}</p><p>Your application is linked to your candidate profile.</p><button className="primary" onClick={onBack}>Explore more opportunities</button></div>}
    </section>
    {step === 'profile' && <CandidateExperience beforeLeaveRef={beforeLeave} opportunity={{ title: role.title, onContinue: value => { if (applicationProfileReady(value)) { setProfile(value); setConfirmed(false); setError(''); setStep('confirm') } } }} />}
  </div></PlatformBackground>
}
