import { UploadCloud } from 'lucide-react'
import type { Resume } from '../types'

export function CandidateWelcome() {
  return <div className="candidate-welcome">
    <h1>Let's find work that feels great.</h1>
    <p>Join Leading Startups Building Their Teams with ENTER</p>
  </div>
}



/** Presentation only: processing, scanning and retry eligibility come from Django. */
export function CandidateProcessing({ resume, uploading, retry, upload, error }: {
  resume: Resume; uploading: boolean; retry: () => void; upload: (file?: File) => void; error: string
}) {
  const failed = resume.processing_status === 'failed'
  const heading = failed ? 'We couldn’t finish this resume'
    : resume.processing_status === 'uploaded' ? 'Your resume is uploaded'
      : resume.processing_status === 'queued' ? 'Your resume is queued'
        : resume.scan_status === 'scanning' ? 'Checking your resume…' : 'Reading your resume…'
  return <section className="candidate-upload-card processing-card" aria-live="polite">
    <div className={`cv-dropzone ${failed ? 'failed' : 'busy'}`}>
      <div className="cv-mark" aria-hidden="true">CV</div>
      <div className="cv-drop-content">
        <h2>{heading}</h2>
        <p>{failed ? resume.processing_error || 'Resume processing failed safely. Your profile was not changed.' : 'Your file is private while we scan it and build your starting profile.'}</p>
        <strong>{resume.original_name}</strong>
        {failed && <div className="processing-actions">
          {resume.can_retry && <button className="primary" onClick={retry} disabled={uploading}>{uploading ? 'Queueing…' : 'Retry processing'}</button>}
          <label className="cv-file-button"><input type="file" aria-label="Upload a replacement resume" accept=".pdf,.docx" onChange={event => upload(event.target.files?.[0])} disabled={uploading} data-testid="resume-input" /><UploadCloud size={18} /><span>Upload a different resume</span></label>
        </div>}
      </div>
    </div>
    {error && <div className="error" role="alert">{error}</div>}
  </section>
}
