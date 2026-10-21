import '@testing-library/jest-dom/vitest'
import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, expect, it } from 'vitest'
import type { WorkExperience } from '../types'
import CandidateCareerTimeline from './CandidateCareerTimeline'
import CareerJourney from './CareerJourney'
import { candidateMilestoneDate } from './candidateMilestoneDate'

afterEach(cleanup)
const role = (overrides: Partial<WorkExperience> = {}): WorkExperience => ({ company: 'Example', role: 'Engineer', start_date: '2018-03-01', end_date: '2019-01-01', description: 'Built reliable tools.', gap_reason: '', ...overrides })
it('respects month precision, year-only extraction and unknown starts', () => {
  expect(candidateMilestoneDate(role())).toBe('2018')
  expect(candidateMilestoneDate(role({ date_label: '2018 – 2019' }))).toBe('2018')
  expect(candidateMilestoneDate(role({ date_label: '2018 - Present' }))).toBe('2018')
  expect(candidateMilestoneDate(role({ start_date: '2018' }))).toBe('2018')
  expect(candidateMilestoneDate(role({ start_date: null }))).toBe('Date unknown')
})
it('retains every role, promotion, overlap, gap, unknown date and keyboard details', () => {
  const items = [role({ role: 'Unknown dates', start_date: null, end_date: null }), role({ role: 'Lead', start_date: '2018-08-01', end_date: '2020-01-01' }), role(), role({ company: 'Next', role: 'Current', start_date: '2021-05-01', end_date: null, gap_reason: 'Study break' })]
  const { container } = render(<CandidateCareerTimeline items={items} />)
  expect(container.querySelectorAll('.career-period')).toHaveLength(4)
  expect(container.querySelectorAll('.career-laptop')).toHaveLength(4)
  expect([...container.querySelectorAll('.career-period small')].map(el => el.textContent)).toEqual(['2018', '2018', '2021', 'Date unknown'])
  fireEvent.focus(screen.getByRole('button', { name: /Lead at Example/ }))
  expect(screen.getByRole('tooltip')).toHaveTextContent('Overlapping employment')
  expect(screen.getByRole('tooltip')).toHaveTextContent('Career progression from Engineer')
  expect(screen.getByRole('tooltip')).toHaveTextContent('Built reliable tools.')
  fireEvent.keyDown(document, { key: 'Escape' })
  expect(screen.queryByRole('tooltip')).toBeNull()
  fireEvent.focus(screen.getByRole('button', { name: /Career gap/ }))
  expect(screen.getByRole('tooltip')).toHaveTextContent('Study break')
  expect(container.querySelector('.career-present-end')).toHaveTextContent('Present')
})
it('shares the laptop marker without changing recruiter dates or details', () => {
  const { container } = render(<CareerJourney items={[role()]} detailed />)
  expect(container.querySelector('.career-laptop')).toHaveAttribute('stroke-width', '1.75')
  expect(container.querySelector('.career-period small')).toHaveTextContent('20182019')
  fireEvent.focus(screen.getByRole('button', { name: /Engineer at Example/ }))
  expect(screen.getByRole('tooltip')).toHaveTextContent('Built reliable tools.')
})
