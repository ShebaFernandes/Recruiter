import { useEffect, useState } from 'react'
import { api } from './api'

export const legalPublished = import.meta.env.VITE_LEGAL_CONTENT_APPROVED === 'true'
export type LegalDocument = { text: string; version: string; sha256: string; effective_date?: string | null; unpublished: boolean }
export type LegalDocuments = Record<'terms' | 'privacy' | 'age' | 'submission', LegalDocument>

export function useLegalDocuments() {
  return useLegalDocumentState().documents
}

export function retryLegalDocuments() {
  window.dispatchEvent(new Event('enter-legal-retry'))
}

export function useLegalDocumentState() {
  const [documents, setDocuments] = useState<LegalDocuments | null>(null)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(legalPublished)
  const [attempt, setAttempt] = useState(0)
  useEffect(() => {
    const retry = () => setAttempt(value => value + 1)
    window.addEventListener('enter-legal-retry', retry)
    return () => window.removeEventListener('enter-legal-retry', retry)
  }, [])
  useEffect(() => {
    if (!legalPublished) return
    let active = true
    // Clear stale content before a refreshed version can be accepted.
    Promise.resolve().then(() => { if (active) { setDocuments(null); setError(''); setLoading(true) } })
    api.legalDocuments().then(result => {
      if (!result.enabled || !result.documents || !['terms', 'privacy', 'age', 'submission'].every(key => {
        const doc = result.documents?.[key as keyof LegalDocuments]
        return doc && doc.text && doc.version && doc.sha256 && doc.unpublished === false
      })) throw new Error('Unavailable documents')
      if (active) setDocuments(result.documents)
    }).catch(() => { if (active) setError('Legal documents could not load. Acceptance is blocked.') })
      .finally(() => { if (active) setLoading(false) })
    return () => { active = false }
  }, [attempt])
  return { documents, loading, error, retry: retryLegalDocuments }
}
