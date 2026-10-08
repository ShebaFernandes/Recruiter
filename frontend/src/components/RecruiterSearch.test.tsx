import '@testing-library/jest-dom/vitest'
import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import RecruiterSearch from './RecruiterSearch'
import type { Search } from '../types'

afterEach(cleanup)
const props = () => ({ query: '', setQuery: vi.fn(), search: null, answer: '', setAnswer: vi.fn(),
  submit: vi.fn(event => event.preventDefault()), clarify: vi.fn(), busy: false, error: '',
  clearProject: vi.fn(), voiceListening: false, startVoiceSearch: vi.fn() })
const clarification: Search = { id: 1, project: null, project_name: '', query: 'Backend engineer with 4 years experience',
  criteria: { role: 'Backend engineer', min_experience: 4 }, state: 'needs_clarification',
  follow_up_question: 'Which location works for your team?', follow_up_options: ['Remote', 'Let me type it'],
  understanding_source: 'deterministic', understanding_model: '', created_at: '' }

describe('recruiter search presentation', () => {
  it('retains suggestion values and focuses the composer without submitting', () => {
    const callbacks = props()
    render(<RecruiterSearch {...callbacks} />)
    expect(screen.getByRole('button', { name: 'Search talent' })).toBeDisabled()
    fireEvent.click(screen.getByRole('button', { name: 'Production ML engineers' }))
    expect(callbacks.setQuery).toHaveBeenCalledWith('Production machine learning engineers with 4 years experience, remote okay')
    expect(screen.getByLabelText('Candidate search')).toHaveFocus()
    expect(callbacks.submit).not.toHaveBeenCalled()
  })
  it('uses a single-line composer and preserves Enter submission without submitting IME composition', () => {
    const callbacks = props()
    render(<RecruiterSearch {...callbacks} query="Backend engineer" />)
    const field = screen.getByLabelText('Candidate search')
    expect(field).toHaveAttribute('type', 'text')
    fireEvent.keyDown(field, { key: 'Enter', isComposing: true })
    expect(callbacks.submit).not.toHaveBeenCalled()
    fireEvent.keyDown(field, { key: 'Enter' })
    expect(callbacks.submit).toHaveBeenCalledTimes(1)
  })
  it('renders only server-supplied clarification and forwards the chosen answer', () => {
    const callbacks = props()
    render(<RecruiterSearch {...callbacks} search={clarification} />)
    expect(screen.getByText(clarification.follow_up_question)).toBeVisible()
    fireEvent.click(screen.getByRole('button', { name: 'Remote' }))
    expect(callbacks.clarify).toHaveBeenCalledWith('Remote')
    fireEvent.click(screen.getByRole('button', { name: 'Let me type it' }))
    expect(screen.getByLabelText('Clarification answer')).toHaveFocus()
  })
  it('keeps busy state and errors real and blocks repeated submit', () => {
    const callbacks = props()
    render(<RecruiterSearch {...callbacks} query="Backend engineer" busy search={clarification} error="Please try again." />)
    expect(screen.getByRole('button', { name: 'Search talent' })).toBeDisabled()
    expect(screen.getByRole('button', { name: 'Remote' })).toBeDisabled()
    expect(screen.getByRole('alert')).toHaveTextContent('Please try again.')
    expect(screen.getByRole('status')).toHaveTextContent('Searching…')
    fireEvent.keyDown(screen.getByLabelText('Candidate search'), { key: 'Enter' })
    expect(callbacks.submit).not.toHaveBeenCalled()
  })
})
