import '@testing-library/jest-dom/vitest'
import { cleanup, render, screen } from '@testing-library/react'
import { afterEach, expect, it, vi } from 'vitest'

vi.hoisted(() => {
  vi.stubEnv('VITE_LEGAL_WORKFLOW_PREVIEW', 'false')
  vi.stubEnv('VITE_LEGAL_CONTENT_APPROVED', 'true')
})

import { api } from '../api'
import type { LegalDocuments } from '../legalReview'
import { ExistingLegalReview, LegalChecks, UnpublishedLegalPage } from './LegalReview'

const documents = Object.fromEntries(['terms', 'privacy', 'age', 'submission'].map(purpose => [purpose, {
  text: `${purpose} v1.0`,
  version: `enter-candidate-${purpose}-v1.0`,
  sha256: 'verified-synthetic-hash',
  effective_date: '2026-10-22',
  unpublished: false,
}])) as LegalDocuments

afterEach(() => { cleanup(); vi.restoreAllMocks() })

it('presents separate production confirmations without recruiter-sharing consent', () => {
  render(<form><LegalChecks documents={documents} /></form>)
  expect(screen.getByRole('group', { name: 'Required confirmations' })).toBeInTheDocument()
  expect(screen.getAllByRole('checkbox')).toHaveLength(2)
  expect(screen.getByRole('link', { name: 'Terms of Use' })).toHaveAttribute('href', '/terms')
  expect(screen.getByText(/does not authorize recruiter sharing/)).toBeInTheDocument()
})

it('shows the immutable published version and effective date', async () => {
  vi.spyOn(api, 'legalDocuments').mockResolvedValue({ enabled: true, documents })
  render(<UnpublishedLegalPage kind="privacy" />)
  expect(await screen.findByText(/Version: enter-candidate-privacy-v1.0 · Effective 2026-10-22/)).toBeInTheDocument()
  expect(screen.queryByText(/UNPUBLISHED/)).not.toBeInTheDocument()
})

it('requires an existing account to accept the current published versions', async () => {
  vi.spyOn(api, 'legalDocuments').mockResolvedValue({ enabled: true, documents })
  vi.spyOn(api, 'legalStatus').mockResolvedValue({
    accepted: { age: false, terms: false },
    versions: { age: documents.age.version, terms: documents.terms.version },
  })
  render(<ExistingLegalReview />)
  expect(await screen.findByRole('heading', { name: 'Review current Terms' })).toBeInTheDocument()
  expect(await screen.findAllByRole('checkbox')).toHaveLength(2)
  expect(screen.getByText(/Existing accounts are not assumed/)).toBeInTheDocument()
})
