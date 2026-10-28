import '@testing-library/jest-dom/vitest'
import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, expect, it, vi } from 'vitest'
import type { WorkExperience } from '../types'
import CandidateCareerTimeline from './CandidateCareerTimeline'
import { roleDateInput, roleMissingDetails } from './careerRoleDates'

afterEach(cleanup)

const role = (overrides: Partial<WorkExperience> = {}): WorkExperience => ({
  id: 12, company: 'Fictional Studio', role: 'Engineer', start_date: '2020-03-01',
  end_date: null, is_current: false, date_label: 'Mar 2020 — End not specified',
  description: '', gap_reason: '', confidence_status: 'supported', ...overrides,
})

it('prompts only for missing details and keeps known fields filled in', () => {
  const save = vi.fn().mockResolvedValue(true)
  render(<CandidateCareerTimeline items={[role()]} saveRole={save} />)
  expect(screen.getByText('1 role needs a date check')).toBeVisible()
  fireEvent.click(screen.getByRole('button', { name: 'Fix dates' }))
  expect(screen.getByRole('textbox', { name: 'Employer' })).toHaveValue('Fictional Studio')
  expect(screen.getByRole('textbox', { name: 'Job title' })).toHaveValue('Engineer')
  expect(screen.getByLabelText('Start date')).toHaveValue('2020-03')
  expect(screen.getByLabelText('End date')).toHaveValue('')
  expect(screen.getAllByLabelText("I don't remember the month")).toHaveLength(1)
  expect(screen.getByRole('button', { name: 'Save' })).toBeDisabled()
})

it('cancels a compact edit without saving or changing the role', () => {
  const save = vi.fn().mockResolvedValue(true)
  render(<CandidateCareerTimeline items={[role()]} saveRole={save} />)
  fireEvent.click(screen.getByRole('button', { name: 'Fix dates' }))
  fireEvent.change(screen.getByRole('textbox', { name: 'Employer' }), {
    target: { value: 'Fictional Workshop' },
  })
  fireEvent.click(screen.getByRole('button', { name: 'Cancel' }))
  expect(screen.queryByRole('form', { name: /Edit Engineer/ })).not.toBeInTheDocument()
  expect(screen.getByRole('button', { name: /Engineer at Fictional Studio/ })).toBeInTheDocument()
  expect(save).not.toHaveBeenCalled()
})

it('saves a year-only correction without inventing a month', async () => {
  const save = vi.fn().mockResolvedValue(true)
  render(<CandidateCareerTimeline items={[role({ start_date: null, date_label: '2020 — 2022' })]} saveRole={save} />)
  expect(screen.queryByRole('button', { name: 'Fix dates' })).not.toBeInTheDocument()
  fireEvent.focus(screen.getByRole('button', { name: /Engineer at Fictional Studio/ }))
  fireEvent.click(screen.getByRole('button', { name: 'Edit this role' }))
  expect(screen.getByLabelText('Start date')).toHaveValue(2020)
  expect(screen.getByLabelText('End date')).toHaveValue(2022)
  fireEvent.change(screen.getByLabelText('Start date'), { target: { value: '2021' } })
  fireEvent.click(screen.getByRole('button', { name: 'Save' }))
  await screen.findByText('Career Journey updated. Your changes are saved.')
  expect(save).toHaveBeenCalledWith(12, { start: { year: 2021, month: null } })
})

it('opens direct editing from a role detail and patches only the changed employer', async () => {
  const save = vi.fn().mockResolvedValue(true)
  render(<CandidateCareerTimeline items={[role({ end_date: '2022-09-01', date_label: 'Mar 2020 — Sep 2022' })]} saveRole={save} />)
  expect(screen.queryByText('1 role needs a date check')).not.toBeInTheDocument()
  fireEvent.focus(screen.getByRole('button', { name: /Engineer at Fictional Studio/ }))
  fireEvent.click(screen.getByRole('button', { name: 'Edit this role' }))
  fireEvent.change(screen.getByRole('textbox', { name: 'Employer' }), { target: { value: 'Fictional Workshop' } })
  fireEvent.click(screen.getByRole('button', { name: 'Save' }))
  await screen.findByText('Career Journey updated. Your changes are saved.')
  expect(save).toHaveBeenCalledWith(12, { company: 'Fictional Workshop' })
})

it('uses the current-role option instead of asking for an end date', async () => {
  const save = vi.fn().mockResolvedValue(true)
  render(<CandidateCareerTimeline items={[role()]} saveRole={save} />)
  fireEvent.click(screen.getByRole('button', { name: 'Fix dates' }))
  fireEvent.click(screen.getByLabelText('I still work here'))
  expect(screen.queryByLabelText('End date')).not.toBeInTheDocument()
  fireEvent.click(screen.getByRole('button', { name: 'Save' }))
  await screen.findByText('Career Journey updated. Your changes are saved.')
  expect(save).toHaveBeenCalledWith(12, { is_current: true })
})

it('offers missing employer or title without labelling a confirmed current role incomplete', () => {
  expect(roleMissingDetails(role({ company: '', role: '', is_current: true,
    date_label: 'Mar 2020 — Present' }))).toEqual(['employer', 'job title'])
  expect(roleMissingDetails(role({ end_date: '2022-09-01', date_label: 'Mar 2020 — Sep 2022' }))).toEqual([])
  expect(roleDateInput(role({ start_date: null, date_label: '2020 — Present' }), 'start')).toEqual({
    month: '', year: '2020', yearOnly: true,
  })
  expect(roleMissingDetails(role({ start_date: null, end_date: null, date_label: '2020 — 2022' }))).toEqual([])
})

it('fills missing employer and title while leaving optional unknown dates untouched', async () => {
  const save = vi.fn().mockResolvedValue(true)
  render(<CandidateCareerTimeline items={[role({ company: '', role: '', start_date: null,
    date_label: 'Dates not specified' })]} saveRole={save} />)
  fireEvent.click(screen.getByRole('button', { name: 'Fix details' }))
  fireEvent.change(screen.getByRole('textbox', { name: 'Employer' }), {
    target: { value: 'Fictional Workshop' },
  })
  fireEvent.change(screen.getByRole('textbox', { name: 'Job title' }), {
    target: { value: 'Developer' },
  })
  fireEvent.click(screen.getByRole('button', { name: 'Save' }))
  await screen.findByText('Career Journey updated. Your changes are saved.')
  expect(save).toHaveBeenCalledWith(12, {
    company: 'Fictional Workshop', role: 'Developer',
  })
})
