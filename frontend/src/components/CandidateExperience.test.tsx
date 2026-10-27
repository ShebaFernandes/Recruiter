import '@testing-library/jest-dom/vitest'
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import CandidateCareerTimeline from './CandidateCareerTimeline'
import CareerJourney from './CareerJourney'
import CandidateResumePreview from './CandidateResumePreview'
import { CandidateProcessing } from './CandidatePresentation'
import { api } from '../api'
import type { Resume, WorkExperience } from '../types'

afterEach(() => { cleanup(); vi.restoreAllMocks() })
const resume: Resume = { id: 9, original_name: 'original.docx', version: 1, uploaded_at: '', processing_status: 'completed', scan_status: 'clean', processing_error: '', can_retry: false, url: '/api/v1/resumes/9/download/' }
const job = (company: string, start_date: string | null, end_date: string | null): WorkExperience => ({ company, role: 'Engineer', start_date, end_date, description: '', gap_reason: '', confidence_status:'candidate_confirmed' })

describe('candidate career experience', () => {
  it('keeps candidate history chronological, ends with Present, and preserves same-year promotions', () => {
    const items = [job('Early company', '2010-01-01', '2020-01-01'),
      { ...job('Recent company', '2021-01-01', '2021-06-01'), role: 'Engineer' },
      { ...job('Recent company', '2021-06-01', null), role: 'Lead', date_label: 'Jun 2021 — Present' }]
    const { container, rerender } = render(<CandidateCareerTimeline items={items} />)
    const roles = () => [...container.querySelectorAll('.career-period>.career-job')]
    expect(roles()).toHaveLength(3)
    expect(roles()[0]).toHaveAttribute('aria-label', expect.stringContaining('Engineer at Early company'))
    expect(container.querySelector('.career-end-year')).toHaveTextContent(String(new Date().getFullYear()))
    expect(roles().map(role => role.querySelector('small')?.textContent)).toEqual(['2010', '2021', '2021'])
    fireEvent.focus(roles()[2])
    expect(screen.getByRole('tooltip')).toHaveTextContent('Recent company')
    expect(screen.getByRole('tooltip')).toHaveTextContent('Lead')
    expect(screen.getByRole('tooltip')).toHaveTextContent('Jun 2021 — Present')
    rerender(<CareerJourney items={items} />)
    expect(roles()[0]).toHaveAttribute('aria-label', expect.stringContaining('Early company'))
    expect(container.querySelector('.career-present')).toBeNull()
  })
  it('keeps recruiter labels while showing candidate facts only in the interactive popover', () => {
    const items = [job('Saved Employer', '2020-01-01', '2022-01-01')]
    const { container, rerender } = render(<CareerJourney items={items} detailed />)
    expect(container.querySelector('.career-job>b')).toBeNull()
    expect(container.querySelector('.career-job>em')).toBeNull()
    rerender(<CandidateCareerTimeline items={items} />)
    expect(container.querySelector('.career-job')).toHaveTextContent('2020')
    expect(container.querySelector('.career-job>b')).toBeNull()
    fireEvent.focus(screen.getByRole('button', { name: /Engineer at Saved Employer/ }))
    expect(screen.getByRole('tooltip')).toHaveTextContent('Saved Employer')
    expect(screen.getByRole('tooltip')).toHaveTextContent('Jan 2020 — Jan 2022')
    fireEvent.keyDown(document, { key: 'Escape' })
    expect(screen.queryByRole('tooltip')).not.toBeInTheDocument()
  })
  it('orders dated jobs and handles overlaps and unknown dates without made-up history', () => {
    render(<CandidateCareerTimeline items={[job('Unknown', null, null), job('Beta', '2021-01-01', null), job('Alpha', '2020-01-01', '2022-01-01')]} />)
    expect(screen.getByRole('button', { name: /at Alpha/ })).toBeVisible()
    expect(screen.getByRole('button', { name: /at Beta/ })).toBeVisible()
    fireEvent.click(screen.getByRole('button', { name: /at Beta/ }))
    expect(screen.getByRole('tooltip')).toHaveTextContent('Beta')
    expect(screen.getByRole('tooltip')).toHaveTextContent('Overlapping employment')
    fireEvent.focus(screen.getByRole('button', { name: /at Alpha/ }))
    fireEvent.click(screen.getByRole('button', { name: /at Alpha/ }))
    expect(screen.getByRole('tooltip')).toHaveTextContent('Alpha')
    fireEvent.keyDown(document, { key: 'Escape' })
    expect(screen.queryByRole('tooltip')).not.toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: /at Unknown/ }))
    expect(screen.getByRole('tooltip')).toHaveTextContent('Unknown')
    expect(screen.getByRole('tooltip')).toHaveTextContent('Start not specified')
    expect(screen.getByRole('tooltip')).not.toHaveTextContent('Present')
  })
  it('provides an editable empty-history fallback', () => {
    render(<CandidateCareerTimeline items={[]} />)
    expect(screen.getByRole('heading', { name: 'Your career journey' })).toBeVisible()
    expect(screen.getByText(/No verified employment history is available/)).toBeVisible()
    expect(screen.queryByRole('listitem')).not.toBeInTheDocument()
  })
  it('labels preserved history as stale when the latest resume needs recovery', () => {
    const { container } = render(<CandidateCareerTimeline items={[job('Previously saved', '2020-01-01', '2022-01-01')]} extraction={{
      status: 'review_required', source: 'rules', reason_code: 'employment_section_not_resolved',
      accepted_role_count: 0, saved_role_count: 1, profile_state: 'previous_history_preserved',
      stale_profile_preserved: true,
    }} />)
    expect(screen.getByRole('status')).toHaveTextContent(/Saved roles remain on the timeline with review-needed markers/i)
    expect(container.querySelector('.career-journey')).toBeInTheDocument()
    expect(container.querySelector('.cp-career-previous')).toBeInTheDocument()
  })
  it('distinguishes successful local fallback from Gemini extraction', () => {
    render(<CandidateCareerTimeline items={[{ ...job('Local result', '2020-01-01', '2022-01-01'), id:1 }]} extraction={{
      resume_id:2, verified_role_ids:[1], status: 'verified_fallback', source: 'rules', reason_code: 'evidence_roles_accepted',
      accepted_role_count: 1, saved_role_count: 1, profile_state: 'applied',
      stale_profile_preserved: false,
    }} />)
    expect(screen.getByRole('status')).toHaveTextContent(/local parser, not Gemini/i)
  })
  it('does not show false gaps inside overlapping employment and exposes real gaps', () => {
    const { rerender } = render(<CandidateCareerTimeline items={[
      job('Long role', '2015-01-01', '2024-01-01'), job('Nested role', '2016-01-01', '2017-01-01'), job('Later role', '2019-01-01', '2020-01-01'),
    ]} />)
    expect(screen.queryByRole('button', { name: /Career gap/ })).not.toBeInTheDocument()
    rerender(<CandidateCareerTimeline items={[job('First', '2015-01-01', '2017-01-01'), { ...job('Second', '2019-01-01', null), gap_reason: 'Study break' }]} />)
    fireEvent.click(screen.getByRole('button', { name: /Career gap/ }))
    expect(screen.getByRole('tooltip')).toHaveTextContent('Career gap')
    expect(screen.getByRole('tooltip')).toHaveTextContent('Study break')
  })
  it('preserves year-only labels without claiming precise durations or gaps', () => {
    render(<CandidateCareerTimeline items={[
      { ...job('First', '2015-01-01', '2017-01-01'), date_label: '2015–17' }, job('Second', '2017-06-01', '2020-01-01'),
    ]} />)
    expect(screen.queryByRole('button', { name: /Career gap/ })).not.toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: /at First/ }))
    expect(screen.getByRole('tooltip')).toHaveTextContent('First')
    expect(screen.getByRole('tooltip')).toHaveTextContent('2015–17')
    expect(screen.getByRole('tooltip')).not.toHaveTextContent('yrs')
  })
  it('displays processing activities without fabricated completed stages', () => {
    render(<CandidateProcessing resume={{ ...resume, processing_status: 'processing' }} uploading={false} retry={vi.fn()} upload={vi.fn()} error="" />)
    expect(screen.getByRole('status')).toHaveTextContent('Processing')
    expect(screen.getAllByRole('listitem')).toHaveLength(4)
    expect(screen.queryByText(/100%|Completed/)).not.toBeInTheDocument()
  })
  it('renders actual document content as escaped text and supports expand/collapse', async () => {
    vi.spyOn(api, 'resumePreview').mockResolvedValue({ blocks: [{ type: 'paragraph', runs: [{ text: '<script>private original text</script>', bold: true, italic: false }] }] })
    const { container } = render(<CandidateResumePreview resume={resume} />)
    fireEvent.click(screen.getByRole('button', { name: 'View Resume' }))
    expect(await screen.findByText('<script>private original text</script>')).toBeVisible()
    expect(container.querySelector('script')).toBeNull()
    fireEvent.click(screen.getByRole('button', { name: 'Maximize resume' }))
    expect(screen.getByRole('dialog')).toBeVisible()
    const minimize = screen.getByRole('button', { name: 'Minimize resume' })
    const documentContent = screen.getByRole('dialog').querySelector<HTMLElement>('.cp-docx')!
    expect(container.querySelector('[role="dialog"]')).toBeNull()
    expect(minimize).toHaveFocus()
    fireEvent.keyDown(document, { key: 'Tab', shiftKey: true })
    expect(documentContent).toHaveFocus()
    fireEvent.keyDown(document, { key: 'Tab' })
    expect(minimize).toHaveFocus()
    fireEvent.keyDown(document, { key: 'Escape' })
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Maximize resume' })).toHaveFocus()
    fireEvent.click(screen.getByRole('button', { name: 'Collapse resume' }))
    expect(screen.queryByText('<script>private original text</script>')).not.toBeInTheDocument()
  })
  it('does not offer quarantined resumes and provides download fallback after errors', async () => {
    const { rerender } = render(<CandidateResumePreview resume={{ ...resume, scan_status: 'quarantined' }} />)
    expect(screen.queryByRole('button')).not.toBeInTheDocument()
    vi.spyOn(api, 'resumePreview').mockRejectedValue(new Error('Preview unavailable'))
    rerender(<CandidateResumePreview resume={resume} />)
    fireEvent.click(screen.getByRole('button', { name: 'View Resume' }))
    await waitFor(() => expect(screen.getByRole('alert')).toHaveTextContent('Preview unavailable'))
    expect(screen.getByRole('link', { name: 'Download original' })).toHaveAttribute('href', resume.url)
  })
})
