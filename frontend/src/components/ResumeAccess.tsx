import { useEffect, useRef, useState } from 'react'
import { Download, FileText } from 'lucide-react'
import { api } from '../api'
import type { Resume } from '../types'

export default function ResumeAccess({ resume }: { resume: Resume | null }) {
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const previewUrls = useRef<string[]>([])
  const mounted = useRef(true)
  useEffect(() => {
    mounted.current = true
    const urls = previewUrls.current
    return () => { mounted.current = false; urls.forEach(url => URL.revokeObjectURL(url)) }
  }, [])
  if (!resume?.url || resume.processing_status !== 'completed' || resume.scan_status !== 'clean') return null
  const isPdf = /\.pdf$/i.test(resume.original_name)

  async function preview() {
    if (!resume) return
    // Open during the user's click, before awaiting fetch, to avoid popup blocking.
    const tab = window.open('about:blank', '_blank')
    if (!tab) { setError('Your browser blocked the preview. Allow a new tab or download the resume below.'); return }
    tab.opener = null
    tab.document.title = 'Opening resume'
    tab.document.body.textContent = 'Opening your authorized resume…'
    setBusy(true); setError('')
    try {
      const file = await api.resumeDocument(resume.id)
      if (!mounted.current || tab.closed) { tab.close(); return }
      if (file.type !== 'application/pdf') throw new Error('Preview is unavailable for this file. Download the resume to open it.')
      const url = URL.createObjectURL(file)
      previewUrls.current.push(url)
      tab.location.replace(url)
    } catch (cause) {
      tab.close()
      if (mounted.current) setError(cause instanceof Error ? cause.message : 'Could not open the resume. Please try again.')
    } finally { if (mounted.current) setBusy(false) }
  }

  return <div className="recruiter-resume-access">
    <div className="resume-access-actions">
      {isPdf ? <button className="primary small" onClick={preview} disabled={busy}><FileText size={16} />{busy ? 'Opening resume…' : 'View Resume'}</button>
        : <a className="primary small" href={resume.url} target="_blank" rel="noopener noreferrer"><FileText size={16} />View Resume</a>}
      <a href={resume.url} target="_blank" rel="noopener noreferrer"><Download size={16} />Download resume</a>
    </div>
    <p>{isPdf ? 'PDF opens in a new tab. If preview is unavailable, download it to your device.' : 'DOCX opens as a download. View it in Word or another compatible document app.'}</p>
    {error && <p role="alert" className="error">{error}</p>}
  </div>
}
