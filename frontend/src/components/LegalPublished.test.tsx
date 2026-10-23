import '@testing-library/jest-dom/vitest'
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, expect, it, vi } from 'vitest'

vi.hoisted(() => {
  vi.stubEnv('VITE_LEGAL_CONTENT_APPROVED', 'true')
})

import { api } from '../api'
import type { LegalDocuments } from '../legalReview'
import { ExistingLegalReview, LegalChecks, LegalPage } from './LegalReview'

const documents = Object.fromEntries(['terms', 'privacy', 'age', 'submission'].map(purpose => [purpose, {
  text: `${purpose} v1.0`,
  version: `enter-candidate-${purpose}-v1.0`,
  sha256: 'verified-synthetic-hash',
  effective_date: '2026-10-22',
  unpublished: false,
}])) as LegalDocuments

afterEach(() => { cleanup(); vi.restoreAllMocks() })

it('presents one explicit 18+ and Terms confirmation without recruiter-sharing consent', () => {
  render(<form><LegalChecks documents={documents} /></form>)
  expect(screen.getByRole('group', { name: 'Required confirmations' })).toBeInTheDocument()
  expect(screen.getAllByRole('checkbox')).toHaveLength(1)
  expect(screen.getByText(/age v1.0/)).toBeInTheDocument()
  expect(screen.getByRole('link', { name: 'Terms of Use' })).toHaveAttribute('href', '/terms')
  expect(screen.getByText(/does not authorize recruiter sharing/)).toBeInTheDocument()
})

it('shows the immutable published version and effective date', async () => {
  vi.spyOn(api, 'legalDocuments').mockResolvedValue({ enabled: true, documents })
  render(<LegalPage kind="privacy" />)
  expect(await screen.findByText(/Version: enter-candidate-privacy-v1.0 · Effective 2026-10-22/)).toBeInTheDocument()
  expect(screen.queryByText(/UNPUBLISHED/)).not.toBeInTheDocument()
})

it('fails closed when an existing account has a stale Terms version', async () => {
  vi.spyOn(api, 'legalDocuments').mockResolvedValue({ enabled: true, documents })
  vi.spyOn(api, 'legalStatus').mockResolvedValue({
    accepted: { age: true, terms: true },
    versions: { age: documents.age.version, terms: 'stale' },
  })
  render(<ExistingLegalReview />)
  expect(await screen.findByRole('button', { name: 'Review current version' })).toBeInTheDocument()
  expect(screen.queryByRole('checkbox')).not.toBeInTheDocument()
})

it('hides the legal review when current signup confirmations are already recorded', async () => {
  vi.spyOn(api, 'legalDocuments').mockResolvedValue({ enabled: true, documents })
  const status = vi.spyOn(api, 'legalStatus').mockResolvedValue({
    accepted: { age: true, terms: true },
    versions: { age: documents.age.version, terms: documents.terms.version },
  })
  render(<ExistingLegalReview />)
  await waitFor(() => expect(status).toHaveBeenCalledOnce())
  expect(screen.queryByRole('heading', { name: /current Terms/ })).not.toBeInTheDocument()
  expect(screen.queryByText(/Current confirmations recorded/)).not.toBeInTheDocument()
})

it('retries a failed published-document request without exposing review content', async () => {
  const load = vi.spyOn(api, 'legalDocuments').mockRejectedValueOnce(new Error('offline'))
    .mockResolvedValue({ enabled: true, documents })
  render(<LegalPage kind="terms" />)
  await screen.findByRole('alert')
  fireEvent.click(screen.getByRole('button', { name: 'Retry legal documents' }))
  await screen.findByText(documents.terms.text)
  await waitFor(() => expect(load).toHaveBeenCalledTimes(2))
  expect(screen.queryByText(/UNPUBLISHED/)).not.toBeInTheDocument()
})

it('requires an existing account to accept the current published versions', async () => {
  vi.spyOn(api, 'legalDocuments').mockResolvedValue({ enabled: true, documents })
  vi.spyOn(api, 'legalStatus')
    .mockResolvedValueOnce({
      accepted: { age: false, terms: false },
      versions: { age: documents.age.version, terms: documents.terms.version },
    })
    .mockResolvedValue({
      accepted: { age: true, terms: true },
      versions: { age: documents.age.version, terms: documents.terms.version },
    })
  const accept = vi.spyOn(api, 'acceptLegal').mockResolvedValue({})
  render(<ExistingLegalReview />)
  expect(await screen.findByRole('heading', { name: 'Accept current Terms' })).toBeInTheDocument()
  expect(await screen.findAllByRole('checkbox')).toHaveLength(1)
  expect(screen.getByText(/Existing accounts are not assumed/)).toBeInTheDocument()
  fireEvent.click(screen.getByRole('checkbox'))
  fireEvent.click(screen.getByRole('button', { name: 'Confirm and continue' }))
  await waitFor(() => expect(accept).toHaveBeenCalledWith(expect.objectContaining({
    age_accepted: true,
    terms_accepted: true,
  })))
  await waitFor(() => expect(screen.queryByRole('heading', { name: 'Accept current Terms' })).not.toBeInTheDocument())
})
