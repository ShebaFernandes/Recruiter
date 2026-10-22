import '@testing-library/jest-dom/vitest'
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, expect, it, vi } from 'vitest'
vi.hoisted(() => vi.stubEnv('VITE_LEGAL_WORKFLOW_PREVIEW', 'true'))
import { api } from '../api'
import { ExistingLegalReview, UnpublishedLegalPage } from './LegalReview'
import type { LegalDocuments } from '../legalReview'

const documents = Object.fromEntries(['terms', 'privacy', 'age', 'submission'].map(p => [p, {
  text: `UNPUBLISHED ${p}`, version: `unpublished-${p}-test`, sha256: 'synthetic', unpublished: true,
}])) as LegalDocuments
const versions = { age: documents.age.version, terms: documents.terms.version }
afterEach(() => { cleanup(); vi.restoreAllMocks() })

it('hides the form for existing current confirmations without creating evidence', async () => {
  vi.spyOn(api, 'legalDocuments').mockResolvedValue({ enabled: true, documents })
  vi.spyOn(api, 'legalStatus').mockResolvedValue({ accepted: { age: true, terms: true }, versions })
  const accept = vi.spyOn(api, 'acceptLegal')
  render(<ExistingLegalReview />)
  await screen.findByText(/Current confirmations recorded/)
  expect(screen.queryByRole('checkbox')).not.toBeInTheDocument()
  expect(accept).not.toHaveBeenCalled()
})

it('shows separate confirmations when current Terms acceptance is missing', async () => {
  vi.spyOn(api, 'legalDocuments').mockResolvedValue({ enabled: true, documents })
  const status = vi.spyOn(api, 'legalStatus').mockResolvedValue({ accepted: { age: true, terms: false }, versions })
  vi.spyOn(api, 'acceptLegal').mockImplementation(async () => {
    status.mockResolvedValue({ accepted: { age: true, terms: true }, versions })
    return {}
  })
  render(<ExistingLegalReview />)
  const checks = await screen.findAllByRole('checkbox')
  expect(checks).toHaveLength(2)
  checks.forEach(check => { expect(check).not.toBeChecked(); fireEvent.click(check) })
  fireEvent.click(screen.getByRole('button', { name: 'Confirm and continue' }))
  await screen.findByText(/Current confirmations recorded/)
  expect(screen.queryByRole('checkbox')).not.toBeInTheDocument()
})

it('fails closed on status/version mismatch', async () => {
  vi.spyOn(api, 'legalDocuments').mockResolvedValue({ enabled: true, documents })
  vi.spyOn(api, 'legalStatus').mockResolvedValue({ accepted: { age: true, terms: true }, versions: { ...versions, terms: 'stale' } })
  render(<ExistingLegalReview />)
  await screen.findByRole('button', { name: 'Review current version' })
  expect(screen.queryByRole('checkbox')).not.toBeInTheDocument()
})

it('reports failed document loading and retries without publishing', async () => {
  const load = vi.spyOn(api, 'legalDocuments').mockRejectedValueOnce(new Error('offline'))
    .mockResolvedValue({ enabled: true, documents })
  render(<UnpublishedLegalPage kind="terms" />)
  await screen.findByRole('alert')
  fireEvent.click(screen.getByRole('button', { name: 'Retry legal documents' }))
  await screen.findByText(documents.terms.text)
  await waitFor(() => expect(load).toHaveBeenCalledTimes(2))
})
