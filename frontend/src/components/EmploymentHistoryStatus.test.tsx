import '@testing-library/jest-dom/vitest'
import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, expect, it } from 'vitest'
import CareerJourney from './CareerJourney'
import CandidateCareerTimeline from './CandidateCareerTimeline'
import type { EmploymentExtraction, WorkExperience } from '../types'

afterEach(cleanup)
const role: WorkExperience = { id:7, company:'Complete Employer Name Private Limited', role:'Senior Platform Engineer', start_date:'2020-01-01', end_date:'2024-01-01', description:'Candidate edited details.', gap_reason:'', confidence_status:'candidate_confirmed' }
const extraction = (status: EmploymentExtraction['status'], extra = {}): EmploymentExtraction => ({ resume_id:2, status, source:'rules', reason_code:'test', accepted_role_count:0, saved_role_count:0, profile_state:'applied', stale_profile_preserved:false, verified_role_ids:[], candidate_confirmed_role_ids:[], unverified_role_ids:[], ...extra })
it.each([CareerJourney, CandidateCareerTimeline])('separates current evidence, explicit no employment and preserved manual history in both views', Component => {
  const { rerender, container } = render(<Component items={[role]} extraction={extraction('verified_ai', { source:'ai', accepted_role_count:1, verified_role_ids:[7] })} />)
  expect(screen.queryByRole('status')).not.toBeInTheDocument()
  expect(container.querySelectorAll('.career-period')).toHaveLength(1)
  rerender(<Component items={[]} extraction={extraction('confirmed_no_employment')} />)
  expect(screen.getByRole('status')).toHaveTextContent('No jobs were listed in this resume')
  rerender(<Component items={[]} extraction={extraction('review_required')} />)
  expect(screen.getByRole('status')).toHaveTextContent('could not verify work history')
  expect(screen.queryByText(/fresher/i)).toBeNull()
  expect(container.querySelector('.career-journey')).toBeNull()
  rerender(<Component items={[role]} extraction={extraction('review_required', { stale_profile_preserved:true, candidate_confirmed_role_ids:[7], unverified_role_ids:[7] })} />)
  expect(container.querySelector('.career-journey')).toBeInTheDocument()
  expect(container.querySelector('.needs-review')).toBeInTheDocument()
  expect(screen.getByRole('status')).toHaveTextContent('Latest resume could not be fully read')
  if (Component === CandidateCareerTimeline) expect(container.querySelector('.career-role-summary')).toBeNull()
  fireEvent.focus(screen.getByRole('button', { name:/Senior Platform Engineer at/ }))
  expect(screen.getByRole('tooltip')).toHaveTextContent('Candidate-confirmed history')
  expect(screen.getByRole('tooltip')).toHaveTextContent('Not matched to the latest resume')
  expect(role.description).toBe('Candidate edited details.')
})
it('offers one explicit no-AI recovery action for an unreadable saved resume', () => {
  let attempts = 0
  render(<CandidateCareerTimeline items={[]} extraction={extraction('review_required')} retryProcessing={() => { attempts++ }} edit={() => { throw new Error('manual edit should not be primary') }} />)
  fireEvent.click(screen.getByRole('button', { name: 'Retry reading resume' }))
  expect(attempts).toBe(1)
})
it('does not certify equally sized old rows or unpublished extraction proposals', () => {
  const { container } = render(<CareerJourney items={[role]} extraction={extraction('verified_ai', { accepted_role_count:1, profile_state:'pending_candidate_review', unverified_role_ids:[7] })} />)
  expect(screen.getByRole('status')).toHaveTextContent('A saved edit differs from the latest resume')
  expect(container.querySelector('.career-journey')).toBeInTheDocument()
})
it('renders all saved rows with distinct verified and review-needed markers', () => {
  const { container } = render(<CareerJourney items={[role, { ...role, id:8, role:'Older saved role' }]} extraction={extraction('verified_fallback', { accepted_role_count:1, verified_role_ids:[7], unverified_role_ids:[8] })} />)
  expect(container.querySelectorAll('.career-sequence')).toHaveLength(2)
  expect(container.querySelectorAll('.career-period')).toHaveLength(1)
  expect(container.querySelectorAll('.career-sequence.needs-review')).toHaveLength(1)
  expect(container.querySelectorAll('.career-sequence.is-verified')).toHaveLength(1)
  expect(screen.queryByRole('status')).not.toBeInTheDocument()
  expect(container.querySelector('.career-journey')).not.toHaveTextContent('Older saved role')
  fireEvent.focus(screen.getByRole('button', { name:/2 roles grouped here/ }))
  expect(screen.getByRole('dialog')).toHaveTextContent('Older saved role')
  expect(screen.getByRole('dialog')).toHaveTextContent('2 roles grouped here')
})
it('draws legacy saved roles with review-needed markers when provenance is missing', () => {
  const { container } = render(<CareerJourney items={[{ ...role, confidence_status:'supported' }]} />)
  expect(container.querySelector('.career-journey')).toBeInTheDocument()
  expect(screen.queryByRole('status')).not.toBeInTheDocument()
})
it('keeps one short ownership notice with saved roles visible', () => {
  const { container } = render(<CandidateCareerTimeline items={[role]} identityWarning="identity_unverified" />)
  const status = screen.getByRole('status')
  expect(status).toHaveTextContent('Resume ownership needs confirmation')
  expect(container.querySelectorAll('.career-history-status')).toHaveLength(1)
  expect(container.querySelector('.career-period')).toBeInTheDocument()
})
it('never presents a completed zero-role result as verified employment', () => {
  render(<CareerJourney items={[]} extraction={extraction('verified_ai', { accepted_role_count:0 })} />)
  expect(screen.getByRole('status')).toHaveTextContent('could not verify work history')
})
