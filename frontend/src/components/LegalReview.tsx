import { useEffect, useState } from 'react'
import { api } from '../api'
import { legalPreview, legalPublished, legalWorkflow, retryLegalDocuments, useLegalDocumentState } from '../legalReview'
import type { LegalDocuments } from '../legalReview'
import { Button } from './ui'
import './legal-review.css'

export function LegalChecks({ documents }: { documents: LegalDocuments }) {
  return <fieldset className="legal-confirmations">
    <legend>{legalPreview ? 'Unpublished local review — not final legal approval' : 'Required confirmations'}</legend>
    <label className="cp-check"><input name="age_accepted" type="checkbox" required /><span>{documents.age.text}</span></label>
    <input type="hidden" name="age_version" value={documents.age.version} />
    <label className="cp-check"><input name="terms_accepted" type="checkbox" required />
      <span>I have read and agree to the <a href="/terms" target="_blank" rel="noopener noreferrer">{legalPreview ? 'unpublished Terms' : 'Terms of Use'}</a> ({documents.terms.version}).</span>
    </label>
    <input type="hidden" name="terms_version" value={documents.terms.version} />
    <p>Read the <a href="/privacy" target="_blank" rel="noopener noreferrer">{legalPreview ? 'unpublished Privacy Policy' : 'Privacy Policy'}</a>. This does not authorize recruiter sharing.</p>
  </fieldset>
}

export function ExistingLegalReview() {
  const { documents, loading, error, retry } = useLegalDocumentState()
  const [message, setMessage] = useState('')
  const [status, setStatus] = useState<Awaited<ReturnType<typeof api.legalStatus>> | null>(null)
  const [statusError, setStatusError] = useState(false)
  const [busy, setBusy] = useState(false)
  const [attempt, setAttempt] = useState(0)
  useEffect(() => {
    if (!documents) return
    let active = true
    api.legalStatus().then(value => { if (active) { setStatus(value); setStatusError(false) } })
      .catch(() => { if (active) { setStatus(null); setStatusError(true) } })
    return () => { active = false }
  }, [documents, attempt])
  if (!legalWorkflow) return null
  const current = documents && status && ['age', 'terms'].every(purpose => {
    const key = purpose as 'age' | 'terms'
    return status.versions[key] === documents[key].version
  })
  const accepted = current && status?.accepted.age && status.accepted.terms
  return <section className="card"><h2>{legalPreview ? 'Local legal review' : 'Review current Terms'}</h2>
    <p>{legalPreview ? 'Unpublished documents.' : 'Current published documents.'} Existing accounts are not assumed to have accepted them.</p>
    {loading && <p role="status">Loading legal documents…</p>}
    {error && <p role="alert">{error} <Button variant="ghost" type="button" onClick={retry}>Retry legal documents</Button></p>}
    {documents && !current && <p role={statusError ? 'alert' : 'status'}>Acceptance status unavailable or version changed. <Button variant="ghost" type="button" onClick={() => { retry(); setAttempt(value => value + 1) }}>Review current version</Button></p>}
    {accepted ? <p role="status">Current confirmations recorded. <a href="/terms">Review Terms</a> · <a href="/privacy">Review Privacy Policy</a></p> : current &&
      <form key={documents.terms.version} onSubmit={async event => {
        event.preventDefault()
        setBusy(true)
        const data = Object.fromEntries(new FormData(event.currentTarget))
        try {
          await api.acceptLegal({ ...data, age_accepted: data.age_accepted === 'on', terms_accepted: data.terms_accepted === 'on' })
          setMessage('Confirmations recorded. No recruiter sharing enabled.')
          setStatus(null)
          setAttempt(value => value + 1)
        } catch (error) { setMessage(error instanceof Error ? error.message : 'Could not record confirmation.'); retry() }
        finally { setBusy(false) }
      }}><LegalChecks documents={documents} /><Button type="submit" disabled={busy}>Confirm and continue</Button></form>}
    <p role="status">{message}</p>
  </section>
}

export function UnpublishedLegalPage({ kind }: { kind: 'terms' | 'privacy' }) {
  const { documents, loading, error, retry } = useLegalDocumentState()
  return <main className="legal-page"><a href="/">Back to ENTER</a><article>
    <h1>{kind === 'terms' ? 'Terms of Use' : 'Privacy Policy'}</h1>
    {legalPreview && <p role="status">UNPUBLISHED — pending final legal wording and sign-off. Not effective.</p>}
    {loading && <p role="status">Loading legal document…</p>}
    {error && <p role="alert">{error} <Button variant="ghost" onClick={retry}>Retry legal documents</Button></p>}
    {documents && <><p>{legalPublished ? 'Version' : 'Review version'}: {documents[kind].version}{documents[kind].effective_date ? ` · Effective ${documents[kind].effective_date}` : ''}</p><pre style={{ whiteSpace: 'pre-wrap', overflowWrap: 'anywhere', font: 'inherit' }}>{documents[kind].text}</pre></>}
  </article></main>
}

export function LegalRetry() {
  return <Button variant="ghost" type="button" onClick={retryLegalDocuments}>Retry / review current legal documents</Button>
}
