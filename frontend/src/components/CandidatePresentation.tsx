import { useEffect, useState } from 'react'
import type { ReactNode } from 'react'
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
export function CandidateProcessing({ resume, uploading, retry, upload, error, refresh, transferring = false, aiConsent }: {
  resume: Resume; uploading: boolean; retry: () => void; upload: (file?: File) => void; error: string; refresh?: () => void; transferring?: boolean; aiConsent?: ReactNode
}) {
  const failed = resume.processing_status === 'failed'
  const active = ['uploaded', 'queued', 'processing'].includes(resume.processing_status)
  const [slow, setSlow] = useState(false)
  useEffect(() => {
    const reset = window.setTimeout(() => setSlow(false), 0)
    const timer = active ? window.setTimeout(() => setSlow(true), 60_000) : undefined
    return () => { window.clearTimeout(reset); window.clearTimeout(timer) }
  }, [active, resume.id, resume.processing_status, resume.processing_stage, resume.scan_status, transferring])
  const delayed = active && (Boolean(error) || slow)
  const stateLabel = transferring ? 'Uploading — transferring your file securely.' : resume.processing_status === 'completed' ? 'Your profile is ready to review.'
    : failed ? 'Processing stopped.'
      : resume.scan_status === 'scanning' ? 'Scanning — checking your file safely.'
        : resume.processing_stage === 'extracting' ? 'Extracting — reading your experience.'
          : resume.processing_stage === 'validating' ? 'Validating — checking and saving your profile.'
        : resume.processing_status === 'processing' ? 'Processing — extracting and validating your experience.'
          : resume.processing_status === 'uploaded' ? 'Uploaded — waiting to be queued.' : 'Queued — waiting for a resume worker.'
  return <section className={`cp-section processing-card ${failed ? 'is-failed' : ''}`} aria-labelledby="resume-processing-heading" tabIndex={-1}>
        <div className="onboarding-processing-copy">
        <h2 id="resume-processing-heading">{failed ? 'We couldn’t finish this resume' : active ? 'While we get to know you…' : 'Your profile is ready'}</h2>
        {active && <p className="cp-processing-intro">We're turning your experience into a clearer picture of your career.</p>}
        <div className={`cp-loading-section ${delayed ? 'is-delayed' : ''}`}>
        {active && <>
          <span className="cp-loading-orbit" aria-hidden="true" />
          <div className={`cp-processing-bar ${delayed ? 'is-paused' : ''}`} role="progressbar" aria-label="Resume processing" aria-valuetext={delayed ? 'Waiting for a processing update' : stateLabel}><span /></div>
        </>}
        <p className="cp-processing-status" role="status">{failed ? stateLabel : error === 'worker_delayed' ? 'Processing is temporarily delayed. Your upload is saved; we’ll keep checking automatically.' : error ? 'Unable to check the latest status. Your upload is saved; we’ll keep checking.' : slow ? 'This is taking longer than expected. We haven’t received a new processing update; we’ll keep checking.' : stateLabel}</p>
        <p className="cp-processing-file">{resume.original_name}</p>
        {delayed && refresh && <div className="processing-actions"><button onClick={refresh} disabled={uploading}>Check status again</button></div>}
        </div>
        {active && <section className="cp-processing-prompts" aria-label="Something to reflect on">
          <p>What would make your next move worth it?</p>
          <ul>{['Harder problems', 'More ownership', 'Exceptional people', 'Compensation'].map(text => <li key={text}>{text}</li>)}</ul>
        </section>}
        {failed && <p role="alert">{error || resume.processing_error || 'Your profile was not changed. Please retry.'}</p>}
        {failed && aiConsent}
        {failed && <div className="processing-actions">
          {resume.can_retry && <button className="primary" onClick={retry} disabled={uploading}>{uploading ? 'Queueing…' : 'Retry processing'}</button>}
          <label className="cv-file-button"><input type="file" aria-label="Upload a replacement resume" accept=".pdf,.docx" onChange={event => upload(event.target.files?.[0])} disabled={uploading} data-testid="resume-input" /><UploadCloud size={18} /><span>Upload a different resume</span></label>
        </div>}
        </div>
  </section>
}
