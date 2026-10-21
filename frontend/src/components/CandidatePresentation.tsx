import { useEffect, useState } from 'react'
import { UploadCloud } from 'lucide-react'
import type { Resume } from '../types'
import EnterBrandText from './EnterBrandText'

export function CandidateWelcome() {
  return <div className="candidate-welcome">
    <h1>Let's find work that feels great.</h1>
    <p><EnterBrandText text="Join Leading Startups Building Their Teams with ENTER" /></p>
  </div>
}



/** Presentation only: processing, scanning and retry eligibility come from Django. */
const activities = ['Reading your experience', 'Mapping your career journey', 'Identifying your strongest skills', "Understanding what you've built", 'Building your ENTER profile']

export function CandidateProcessing({ resume, uploading, retry, upload, error, refresh, transferring = false }: {
  resume: Resume; uploading: boolean; retry: () => void; upload: (file?: File) => void; error: string; refresh?: () => void; transferring?: boolean
}) {
  const failed = resume.processing_status === 'failed'
  const active = ['uploaded', 'queued', 'processing'].includes(resume.processing_status)
  const [activity, setActivity] = useState(0)
  useEffect(() => {
    if (!active || error || typeof window.matchMedia !== 'function') return
    const motion = window.matchMedia('(prefers-reduced-motion: reduce)')
    let timer: number | undefined
    const update = () => {
      window.clearInterval(timer)
      if (!motion.matches) timer = window.setInterval(() => setActivity(value => (value + 1) % activities.length), 3000)
    }
    update(); motion.addEventListener('change', update)
    return () => { window.clearInterval(timer); motion.removeEventListener('change', update) }
  }, [active, error])
  const stateLabel = transferring ? 'Uploading — transferring your file securely.' : resume.processing_status === 'completed' ? 'Your profile is ready to review.'
    : failed ? 'Processing stopped.'
      : resume.scan_status === 'scanning' ? 'Scanning — checking your file safely.'
        : resume.processing_status === 'processing' ? 'Processing — preparing your profile.'
          : resume.processing_status === 'uploaded' ? 'Uploaded — waiting to be queued.' : 'Queued — waiting for a resume worker.'
  return <section className={`cp-section processing-card ${failed ? 'is-failed' : ''}`} aria-labelledby="resume-processing-heading" tabIndex={-1}>
        <div className="onboarding-processing-copy">
        <h2 id="resume-processing-heading">{failed ? 'We couldn’t finish this resume' : active ? "We're doing the boring part." : 'Your profile is ready'}</h2>
        <p className="cp-processing-file">{resume.original_name}</p>
        {active && <>
          <div className="cp-processing-message" aria-hidden="true"><span key={activity}><EnterBrandText text={activities[activity]} /></span></div>
          <ul className="sr-only" aria-label="Profile preparation activities, not completed stages">{activities.map(text => <li key={text}>{text}</li>)}</ul>
          <div className={`cp-processing-bar ${error ? 'is-paused' : ''}`} role="progressbar" aria-label="Resume processing" aria-valuetext={error ? 'Status temporarily unavailable' : stateLabel}><span /></div>
        </>}
        <p className="cp-processing-status" role="status">{error === 'worker_delayed' ? 'Processing is temporarily delayed. Your upload is saved; we’ll keep checking automatically.' : error ? 'Unable to check the latest status. Your upload is saved; we’ll keep checking.' : stateLabel}</p>
        {error && active && refresh && <div className="processing-actions"><button onClick={refresh} disabled={uploading}>Check status again</button></div>}
        {failed && <p role="alert">{error || resume.processing_error || 'Your profile was not changed. Please retry.'}</p>}
        {failed && <div className="processing-actions">
          {resume.can_retry && <button className="primary" onClick={retry} disabled={uploading}>{uploading ? 'Queueing…' : 'Retry processing'}</button>}
          <label className="cv-file-button"><input type="file" aria-label="Upload a replacement resume" accept=".pdf,.docx" onChange={event => upload(event.target.files?.[0])} disabled={uploading} data-testid="resume-input" /><UploadCloud size={18} /><span>Upload a different resume</span></label>
        </div>}
        </div>
  </section>
}
