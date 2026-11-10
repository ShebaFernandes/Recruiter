import { applicationCvReady, applicationProfileReady } from '../opportunityApplication'
import { useEffect, useRef, useState } from 'react'
import { api } from '../api'
import type { Candidate } from '../types'
import CandidateExperience from './CandidateExperience'
import { LogOut, FileText, LockKeyhole, UploadCloud } from 'lucide-react'
import CandidateFooter from './CandidateFooter'
import PlatformBackground from './PlatformBackground'
import { CandidateProcessing } from './CandidatePresentation'
import './opportunity-application.css'


export default function OpportunityApplication({ role, onBack, embedded = false }: {
  role: { id: string; title: string }; onBack: () => void; embedded?: boolean
}) {
  const [step, setStep] = useState<'cv' | 'profile' | 'confirm' | 'success'>('cv')
  const [waitingForCv, setWaitingForCv] = useState(false)
  const [profile, setProfile] = useState<Candidate | null>(null)
  const [error, setError] = useState('')
  const [attempt, setAttempt] = useState(0)
  const [note, setNote] = useState('')
  const [confirmed, setConfirmed] = useState(false)
  const [busy, setBusy] = useState(false)
  const [dragging, setDragging] = useState(false)
  const [message, setMessage] = useState('')
  const beforeLeave = useRef<(() => Promise<boolean>) | null>(null)
  const heading = useRef<HTMLHeadingElement>(null)
  const workspace = useRef<HTMLDivElement>(null)
  useEffect(() => {
    let active = true
    api.candidateProfile().then(value => {
      if (active) {
        setProfile(value)
        setError('')
        // Skip CV selection if candidate already has a usable CV
        if (applicationCvReady(value)) {
          setStep('confirm')
        } else if (['uploaded', 'queued', 'processing'].includes(value.latest_resume?.processing_status || '')) {
          setWaitingForCv(true)
        }
      }
    })
      .catch(cause => { if (active) setError(cause instanceof Error ? cause.message : 'Could not open your profile.') })
    return () => { active = false }
  }, [attempt])
  useEffect(() => {
    if (!waitingForCv) return
    let active = true
    const timer = window.setInterval(() => {
      api.candidateProfile().then(value => {
        if (!active) return
        setProfile(value)
        if (applicationCvReady(value)) { setWaitingForCv(false); setStep('confirm') }
        else if (value.latest_resume?.processing_status === 'failed') { setWaitingForCv(false); setError('Your CV could not be processed. Please try another file.'); setStep('cv') }
      }).catch(() => { /* The profile screen offers processing recovery. */ })
    }, 2000)
    return () => { active = false; window.clearInterval(timer) }
  }, [waitingForCv])
  useEffect(() => { workspace.current?.scrollTo?.(0, 0); (step === 'profile' ? workspace.current : heading.current)?.focus(); window.scrollTo(0, 0) }, [step])
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
    try { setProfile(await api.uploadResume(file)); setWaitingForCv(true); setStep('profile') }
    catch (cause) { setError(cause instanceof Error ? cause.message : 'Could not upload your CV. Please try again.') }
    finally { setBusy(false) }
  }
  async function retry() {
    if (!profile?.latest_resume || busy) return
    setBusy(true); setError('')
    try { setProfile(await api.retryResume(profile.latest_resume.id)); setWaitingForCv(true) }
    catch (cause) { setError(cause instanceof Error ? cause.message : 'Could not retry processing. Please try again.') }
    finally { setBusy(false) }
  }
  async function submit(event: React.FormEvent) {
    event.preventDefault()
    if (busy || !confirmed || !profile) return
    setBusy(true); setError('')
    try {
      const current = await api.candidateProfile()
      if (!applicationCvReady(current) || current.latest_resume?.id !== profile.latest_resume?.id || current.profile_updated_at !== profile.profile_updated_at) {
        setProfile(current); setConfirmed(false); setStep('profile')
        setError('Your CV or profile has changed. Please review it again before applying.')
        return
      }
      const result = await api.applyOpportunity(role.id, note)
      setMessage(result.detail); setStep('success')
      sessionStorage.removeItem('enter-opportunity-intent'); sessionStorage.removeItem('enter-opportunity-action')
    } catch (cause) { setError(cause instanceof Error ? cause.message : 'Could not submit. Please try again.') }
    finally { setBusy(false) }
  }
  return <PlatformBackground><div className={`opportunity-application-page is-${step}`}>
    {embedded ? <nav className="opp-embedded-back" aria-label="Application navigation"><button type="button" disabled={busy} onClick={() => void back()}>← Back to opportunities</button></nav> : <header className="opp-header"><div className="opp-application-brand"><a href="/" aria-label="Enter home"><div className="brand brand-compact"><img src="/enter-logo.jpeg" alt="enter" /><span>Talent Platform</span></div></a></div><div className="opp-application-navigation"><button type="button" disabled={busy} onClick={() => void back()}>Back to opportunities<LogOut size={16} aria-hidden="true" /></button></div></header>}
    <div ref={workspace} tabIndex={-1} className="opportunity-application-workspace">
    <section className="opp-application-shell" style={step === 'profile' && !error ? { display: 'none' } : undefined}>
      {step !== 'profile' && <>{step === 'success' && <p className="opp-eyebrow">APPLICATION RECEIVED</p>}
      <h1 ref={heading} tabIndex={-1}>{step === 'cv' ? 'ENTER what’s next?' : role.title}</h1></>}
      {step === 'cv' && <><p className="opp-application-intro">Somewhere, there’s something worth building.</p><p className="opp-selected-role">Applying for <strong>{role.title}</strong></p></>}
      {error && <p role="alert" className="error">{error}</p>}
      {step === 'cv' && (!profile ? <><p role="status">{error ? 'Your profile could not be loaded.' : 'Opening your profile…'}</p>{error && <button onClick={() => { setError(''); setAttempt(value => value + 1) }}>Try again</button>}</> : profile.latest_resume && ['uploaded', 'queued', 'processing', 'failed'].includes(profile.latest_resume.processing_status) ? <CandidateProcessing resume={profile.latest_resume} uploading={busy} retry={() => void retry()} upload={file => void upload(file)} error="" refresh={() => setAttempt(value => value + 1)} /> : <>
        {<section className="opp-cv-panel" aria-labelledby="opp-cv-title">
          <header><FileText aria-hidden="true" /><div><h2 id="opp-cv-title">{profile.latest_resume ? 'Choose your CV' : 'Start with your CV'}</h2><p>Your experience deserves to be understood.</p></div></header>
          {profile.latest_resume && <div className="opp-current-cv"><div><span>YOUR CURRENT CV</span><p>{profile.latest_resume.original_name}</p>{profile.latest_resume.processing_status === 'completed' && profile.latest_resume.scan_status !== 'clean' && <p role="alert">This file didn’t pass our security scan. Please upload a different CV.</p>}{profile.latest_resume.processing_status === 'completed' && profile.latest_resume.scan_status === 'clean' && profile.resume_identity_warning && <p role="alert">We couldn’t confirm this CV belongs to you. Please review it in your profile, or upload a different one.</p>}</div>{applicationCvReady(profile) && <button className="primary" disabled={busy} onClick={() => setStep('profile')}>Use current CV</button>}</div>}
          <div className={`opp-cv-dropzone${dragging ? ' is-dragging' : ''}`} onDragOver={event => { event.preventDefault(); if (!busy) setDragging(true) }} onDragLeave={event => { if (!event.currentTarget.contains(event.relatedTarget as Node | null)) setDragging(false) }} onDrop={event => { event.preventDefault(); setDragging(false); if (!busy) void upload(event.dataTransfer.files[0]) }} aria-busy={busy}>
            <UploadCloud aria-hidden="true" />
            <p>{busy ? 'Uploading your CV…' : profile.latest_resume ? 'Drop your updated CV here' : 'Drop your CV here'}</p>
            <label className="opp-cv-upload"><span>{busy ? 'Uploading…' : profile.latest_resume ? 'Choose updated CV' : 'Choose your CV'}</span><input aria-label={profile.latest_resume ? 'Upload updated CV' : 'Upload your CV'} type="file" accept=".pdf,.docx" disabled={busy} onChange={event => { void upload(event.target.files?.[0]); event.target.value = '' }} /></label>
            <small>PDF or DOCX · Max 5 MB</small>
          </div>
          <p className="opp-cv-privacy"><LockKeyhole size={16} aria-hidden="true" />Private upload · Review your profile before submitting</p>
        </section>}
      </>)}
      {step === 'confirm' && profile && <form onSubmit={event => void submit(event)} className="opp-application">
        <h2>Review your application</h2><p><strong>{profile.full_name}</strong>{profile.location && ` · ${profile.location}`}</p><p>CV: {profile.latest_resume?.original_name}</p>
        <div className="opp-cv-actions">{profile.latest_resume?.url && <a href={profile.latest_resume.url} target="_blank" rel="noopener noreferrer">View CV</a>}
        <button type="button" disabled={busy} onClick={() => { setConfirmed(false); setStep('cv') }}>Replace CV</button>
        <button type="button" disabled={busy} onClick={() => { setConfirmed(false); setStep('profile') }}>Edit CV or profile</button></div>
        <label>Anything you’d like us to know? (optional)<textarea value={note} onChange={event => setNote(event.target.value)} maxLength={5000} rows={5} disabled={busy} /></label>
        <label className="cp-check"><input type="checkbox" checked={confirmed} onChange={event => setConfirmed(event.target.checked)} disabled={busy} required />I have reviewed my CV and profile and want to apply for {role.title}.</label>
        <p>This application is linked to your saved candidate profile. It does not change your recruiter sharing preferences.</p>
        <button className="primary" disabled={busy || !confirmed}>{busy ? 'Submitting…' : 'Submit application'}</button>
      </form>}
      {step === 'success' && <div role="status"><h2>{message}</h2><p>Role: {role.title}</p><p>Your application is linked to your candidate profile.</p><button className="primary" onClick={onBack}>Explore more opportunities</button></div>}
    </section>
    {step === 'profile' && <CandidateExperience beforeLeaveRef={beforeLeave} opportunity={{ title: role.title, onContinue: value => { if (applicationProfileReady(value)) { setProfile(value); setConfirmed(false); setError(''); setStep('confirm') } } }} />}
    <div className="candidate-experience application-help-footer"><CandidateFooter /></div>
    </div>
  </div></PlatformBackground>
}
