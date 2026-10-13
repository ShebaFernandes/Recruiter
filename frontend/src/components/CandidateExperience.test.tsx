import '@testing-library/jest-dom/vitest'
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import CandidateCareerTimeline from './CandidateCareerTimeline'
import CandidateResumePreview from './CandidateResumePreview'
import { CandidateProcessing } from './CandidatePresentation'
import { api } from '../api'
import type { Resume, WorkExperience } from '../types'

afterEach(() => { cleanup(); vi.restoreAllMocks() })
const resume: Resume = { id: 9, original_name: 'original.docx', version: 1, uploaded_at: '', processing_status: 'completed', scan_status: 'clean', processing_error: '', can_retry: false, url: '/api/v1/resumes/9/download/' }
const job = (company: string, start_date: string | null, end_date: string | null): WorkExperience => ({ company, role: 'Engineer', start_date, end_date, description: '', gap_reason: '' })

describe('candidate career experience', () => {
  it('orders dated jobs and handles overlaps and unknown dates without made-up history', () => {
    render(<CandidateCareerTimeline items={[job('Unknown', null, null), job('Beta', '2021-01-01', null), job('Alpha', '2020-01-01', '2022-01-01')]} />)
    const rows = screen.getAllByRole('listitem')
    expect(rows[0]).toHaveTextContent('Alpha')
    expect(rows[1]).toHaveTextContent('Beta')
    expect(rows[1]).toHaveTextContent('Overlapping role')
    expect(rows[2]).toHaveTextContent('Start not specified')
  })
  it('provides an editable empty-history fallback', () => {
    render(<CandidateCareerTimeline items={[]} />)
    expect(screen.getByText(/No career history identified/)).toBeVisible()
    expect(screen.queryByRole('listitem')).not.toBeInTheDocument()
  })
  it('displays processing activities without fabricated completed stages', () => {
    render(<CandidateProcessing resume={{ ...resume, processing_status: 'processing' }} uploading={false} retry={vi.fn()} upload={vi.fn()} error="" />)
    expect(screen.getByText('Mapping your career journey')).toBeVisible()
    expect(screen.getAllByRole('listitem')).toHaveLength(5)
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
    const documentContent = container.querySelector<HTMLElement>('.cp-docx')!
    expect(minimize).toHaveFocus()
    fireEvent.keyDown(document, { key: 'Tab', shiftKey: true })
    expect(documentContent).toHaveFocus()
    fireEvent.keyDown(document, { key: 'Tab' })
    expect(minimize).toHaveFocus()
    fireEvent.keyDown(document, { key: 'Escape' })
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
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
