import { useEffect, useRef, useState } from 'react'
import { createPortal } from 'react-dom'
import { api } from '../api'
import type { DocumentPreview, Resume } from '../types'
import { Download, Maximize2, Minimize2, X, FileText } from 'lucide-react'

export default function CandidateResumePreview({ resume }: { resume: Resume | null }) {
  const [open, setOpen] = useState(false)
  const [expanded, setExpanded] = useState(false)
  const [url, setUrl] = useState('')
  const [document, setDocument] = useState<DocumentPreview | null>(null)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const panel = useRef<HTMLDivElement>(null)
  const trigger = useRef<HTMLButtonElement>(null)
  const wasExpanded = useRef(false)
  const id = resume?.id
  const pdf = /\.pdf$/i.test(resume?.original_name || '')
  useEffect(() => {
    if (!open || !id) return
    let active = true
    let objectUrl = ''
    const load = async () => {
      try {
        if (pdf) {
          const blob = await api.resumeDocument(id)
          if (active) { objectUrl = URL.createObjectURL(blob); setUrl(objectUrl) }
        } else {
          const data = await api.resumePreview(id)
          if (active) setDocument(data)
        }
      } catch (cause) { if (active) setError(cause instanceof Error ? cause.message : 'Preview unavailable.') }
      finally { if (active) setBusy(false) }
    }
    void load()
    return () => { active = false; if (objectUrl) URL.revokeObjectURL(objectUrl) }
  }, [id, open, pdf])
  useEffect(() => {
    if (!expanded) {
      // The portal remounts inline on minimize; restore keyboard focus to its new control.
      if (wasExpanded.current) panel.current?.querySelector<HTMLButtonElement>('button')?.focus()
      wasExpanded.current = false
      return
    }
    wasExpanded.current = true
    const previous = window.document.activeElement as HTMLElement | null
    const previousOverflow = window.document.body.style.overflow
    window.document.body.style.overflow = 'hidden'
    panel.current?.querySelector<HTMLButtonElement>('button')?.focus()
    const keydown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') { setExpanded(false); return }
      if (event.key !== 'Tab') return
      const controls = panel.current?.querySelectorAll<HTMLElement>('button,a[href],iframe,[tabindex="0"]')
      if (!controls?.length) return
      const first = controls[0], last = controls[controls.length - 1]
      if (event.shiftKey && window.document.activeElement === first) { event.preventDefault(); last.focus() }
      else if (!event.shiftKey && window.document.activeElement === last) { event.preventDefault(); first.focus() }
    }
    window.document.addEventListener('keydown', keydown)
    return () => { window.document.body.style.overflow = previousOverflow; window.document.removeEventListener('keydown', keydown); previous?.focus() }
  }, [expanded])
  if (!resume?.url || resume.scan_status !== 'clean' || resume.processing_status !== 'completed') return null
  const preview = <div id="candidate-resume-preview" ref={panel} className={`cp-resume-panel ${expanded ? 'expanded' : ''}`} role={expanded ? 'dialog' : 'region'} aria-modal={expanded || undefined} aria-label="Uploaded resume">
      <div className="cp-resume-toolbar"><div className="cp-document-name"><FileText size={18} aria-hidden="true" /><strong title={resume.original_name}>{resume.original_name}</strong></div><div className="cp-resume-controls"><button aria-label={expanded ? 'Minimize resume' : 'Maximize resume'} title={expanded ? 'Minimize resume' : 'Maximize resume'} onClick={() => setExpanded(!expanded)}>{expanded ? <Minimize2 size={16} /> : <Maximize2 size={16} />}</button><a href={resume.url} target="_blank" rel="noopener noreferrer"><Download size={16} aria-hidden="true" />Download original</a><button aria-label="Collapse resume" title="Close preview" onClick={() => { setOpen(false); setExpanded(false); trigger.current?.focus() }}><X size={16} /></button></div></div>
      {busy && <p role="status">Opening your resume…</p>}
      {error && <p role="alert">{error} Use Download original, or close and reopen to retry.</p>}
      {url && <><p className="cp-muted">If your browser cannot display the PDF, use Download original.</p><iframe title="Original PDF resume" src={url} /></>}
      {document && <><p className="cp-muted">DOCX document content. Layout and embedded artwork may differ; download the original for full fidelity.</p><div className="cp-docx" tabIndex={0}>{document.blocks.map((block, i) => block.type === 'paragraph' ? <p key={i}>{block.runs.map((run, j) => <span key={j} style={{ fontWeight: run.bold ? 700 : undefined, fontStyle: run.italic ? 'italic' : undefined }}>{run.text}</span>)}</p> : <table key={i}><tbody>{block.rows.map((row, j) => <tr key={j}>{row.map((cell, k) => <td key={k}>{cell}</td>)}</tr>)}</tbody></table>)}</div></>}
    </div>
  return <section className="cp-resume">
    <div className="cp-resume-heading"><h3>Resume</h3><p>View your latest uploaded resume.</p></div>
    <button ref={trigger} type="button" aria-expanded={open} aria-controls="candidate-resume-preview" onClick={() => { setOpen(!open); setExpanded(false); setBusy(!open); setError(''); setUrl(''); setDocument(null) }}>{open ? 'Hide Resume' : 'View Resume'}</button>
    {/* Escape backdrop-filter containing blocks while retaining candidate control styling. */}
    {open && (expanded ? createPortal(<div className="candidate-experience" style={{ display: 'contents' }}>{preview}</div>, window.document.body) : preview)}
  </section>
}
