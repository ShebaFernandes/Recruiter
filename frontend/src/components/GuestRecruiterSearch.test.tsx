import '@testing-library/jest-dom/vitest'
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { api } from '../api'
import type { GuestSearch } from '../types'
import GuestRecruiterSearch from './GuestRecruiterSearch'

afterEach(() => { cleanup(); vi.restoreAllMocks() })

const brief: GuestSearch = {
  id: 'guest', token: 'server-signed-test-token', query: 'Backend engineer with 4 years experience',
  criteria: { role: 'Backend engineer', min_experience: 4, notice_period_days: null },
  state: 'needs_clarification', follow_up_question: 'Are remote candidates okay?',
  follow_up_options: ['Remote', 'Let me type it'], understanding_source: 'openrouter', understanding_model: 'test',
}

describe('guest recruiter boundary', () => {
  it('submits only to guest APIs and shows a brief, never candidate results', async () => {
    const start = vi.spyOn(api, 'guestSearch').mockResolvedValue(brief)
    const answer = vi.spyOn(api, 'guestAnswer').mockResolvedValue({ ...brief, state: 'complete', criteria: { ...brief.criteria, notice_period_days: 0 }, follow_up_question: '' })
    const privateSearch = vi.spyOn(api, 'createSearch')
    const results = vi.spyOn(api, 'results')
    const workspace = vi.fn()
    render(<GuestRecruiterSearch home={vi.fn()} workspace={workspace} />)
    expect(start).not.toHaveBeenCalled()
    fireEvent.change(screen.getByLabelText('Candidate search'), { target: { value: brief.query } })
    fireEvent.click(screen.getByRole('button', { name: 'Search talent' }))
    expect(await screen.findByText(brief.follow_up_question)).toBeVisible()
    fireEvent.click(screen.getByRole('button', { name: 'Remote' }))
    const heading = await screen.findByRole('heading', { name: 'Your search brief is ready' })
    expect(heading).toHaveFocus()
    expect(screen.getByText('0', { exact: true })).toBeVisible()
    expect(answer).toHaveBeenCalledWith(brief.token, 'Remote')
    expect(privateSearch).not.toHaveBeenCalled()
    expect(results).not.toHaveBeenCalled()
    fireEvent.click(screen.getByRole('button', { name: 'Open protected recruiter workspace' }))
    expect(workspace).toHaveBeenCalledOnce()
  })

  it('shows rate-limit recovery without retrying automatically', async () => {
    const request = vi.spyOn(api, 'guestSearch').mockRejectedValue(new Error('Guest search has reached its request limit. Please try again later.'))
    render(<GuestRecruiterSearch home={vi.fn()} workspace={vi.fn()} />)
    fireEvent.change(screen.getByLabelText('Candidate search'), { target: { value: 'Backend engineer' } })
    fireEvent.click(screen.getByRole('button', { name: 'Search talent' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('request limit')
    await waitFor(() => expect(screen.getByRole('button', { name: 'Search talent' })).toBeEnabled())
    expect(request).toHaveBeenCalledOnce()
  })
})
