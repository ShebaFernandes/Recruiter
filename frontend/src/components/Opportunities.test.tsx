import '@testing-library/jest-dom/vitest'
import { cleanup, fireEvent, render, screen, within } from '@testing-library/react'
import { afterEach, expect, it, vi } from 'vitest'
import Opportunities from './Opportunities'
import { api } from '../api'
import type { Candidate } from '../types'

afterEach(() => { cleanup(); vi.restoreAllMocks(); sessionStorage.clear() })
it('applies inline using the existing CV without opening the review screen', async () => {
  sessionStorage.setItem('enter-opportunity-intent', 'backend-engineer')
  vi.spyOn(api, 'candidateProfile').mockResolvedValue({
    latest_resume: { id: 1, processing_status: 'completed', scan_status: 'clean' },
  } as Candidate)
  vi.spyOn(api, 'opportunityApplications').mockResolvedValue([])
  const submit = vi.spyOn(api, 'applyOpportunity').mockResolvedValue({ detail: 'Your application has been received.' })
  render(<Opportunities loggedIn onLogin={vi.fn()} />)
  fireEvent.click(await screen.findByRole('button', { name: 'Apply now' }))
  expect(await screen.findByText('Your application has been received.')).toBeVisible()
  expect(submit).toHaveBeenCalledWith('backend-engineer', '')
  expect(screen.getByRole('button', { name: 'Already applied' })).toBeDisabled()
  expect(screen.queryByRole('heading', { name: 'Review your application' })).not.toBeInTheDocument()
})

it('notifies the originating screen when application details close', async () => {
  sessionStorage.setItem('enter-opportunity-intent', 'backend-engineer')
  const close = vi.fn()
  render(<Opportunities loggedIn onLogin={vi.fn()} onDetailClose={close} />)
  fireEvent.click(await screen.findByRole('button', { name: 'Close job description' }))
  expect(close).toHaveBeenCalledOnce()
})

it('shows submitted status without an Apply button in application details', async () => {
  sessionStorage.setItem('enter-opportunity-intent', 'backend-engineer')
  render(<Opportunities loggedIn applicationDetails onLogin={vi.fn()} />)
  expect(await screen.findByText('Application submitted')).toBeVisible()
  expect(screen.queryByRole('button', { name: 'Apply now' })).not.toBeInTheDocument()
})

it('loads already-applied status from saved applications', async () => {
  sessionStorage.setItem('enter-opportunity-intent', 'backend-engineer')
  vi.spyOn(api, 'opportunityApplications').mockResolvedValue([{id:1, opportunity_id:'backend-engineer', created_at:'2026-11-04T00:00:00Z'}])
  const submit = vi.spyOn(api, 'applyOpportunity')
  render(<Opportunities loggedIn onLogin={vi.fn()} />)
  expect(await screen.findByRole('button', { name:'Already applied' })).toBeDisabled()
  expect(submit).not.toHaveBeenCalled()
})


it('opens the chosen JD with its description and role facts, then closes it', async () => {
  render(<Opportunities loggedIn={false} onLogin={vi.fn()} />)
  const listing = screen.getByRole('button', { name: 'Lead Product Manager — Consumer' })
    .closest('article')!
  fireEvent.click(within(listing).getByRole('button', { name: 'View Opportunity' }))
  const dialog = screen.getByRole('dialog', { name: 'Job description' })
  expect(within(dialog).getByRole('heading', { name: 'Lead Product Manager — Consumer' })).toBeVisible()
  expect(within(dialog).getByText(/Own the complete product roadmap/)).toBeVisible()
  const summary = within(dialog).getByRole('complementary', { name: 'Opportunity summary' })
  expect(within(summary).getByText('Lead Product Manager — Consumer')).toBeVisible()
  expect(within(dialog).getByText('₹80 LPA')).toBeVisible()
  expect(within(dialog).getByText('Bengaluru')).toBeVisible()
  expect(within(dialog).getByText('8+ years')).toBeVisible()
  fireEvent.click(within(dialog).getByRole('button', { name: 'Close job description' }))
  expect(screen.queryByRole('dialog', { name: 'Job description' })).not.toBeInTheDocument()
})

it('uses the latest close callback without resetting dialog focus', async () => {
  sessionStorage.setItem('enter-opportunity-intent', 'backend-engineer')
  vi.spyOn(api, 'opportunityApplications').mockResolvedValue([])
  const previous = vi.fn(), current = vi.fn(), login = vi.fn()
  const view = render(<Opportunities loggedIn onLogin={login} onDetailClose={previous} />)
  const apply = await screen.findByRole('button', { name: 'Apply now' })
  apply.focus()
  view.rerender(<Opportunities loggedIn onLogin={login} onDetailClose={current} />)
  expect(apply).toHaveFocus()
  fireEvent.keyDown(document, { key: 'Escape' })
  expect(previous).not.toHaveBeenCalled()
  expect(current).toHaveBeenCalledOnce()
})
