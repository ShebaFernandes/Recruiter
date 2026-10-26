import '@testing-library/jest-dom/vitest'
import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, expect, it } from 'vitest'
import type { WorkExperience } from '../types'
import CandidateCareerTimeline from './CandidateCareerTimeline'
import CareerJourney from './CareerJourney'
import { candidateMilestoneDate } from './candidateMilestoneDate'
import { sortCareerHistory } from '../careerHistory'

afterEach(cleanup)
const role = (overrides: Partial<WorkExperience> = {}): WorkExperience => ({ company: 'Example', role: 'Engineer', start_date: '2018-03-01', end_date: '2019-01-01', description: 'Built reliable tools.', gap_reason: '', ...overrides })
it('respects month precision, year-only extraction and unknown starts', () => {
  expect(candidateMilestoneDate(role())).toBe('2018')
  expect(candidateMilestoneDate(role({ date_label: '2018 – 2019' }))).toBe('2018')
  expect(candidateMilestoneDate(role({ date_label: '2018 - Present' }))).toBe('2018')
  expect(candidateMilestoneDate(role({ start_date: '2018' }))).toBe('2018')
  expect(candidateMilestoneDate(role({ start_date: null, date_label: '2018 — 19' }))).toBe('2018')
  expect(candidateMilestoneDate(role({ start_date: null }))).toBe('Date unknown')
})
it('sorts year-only promotions chronologically without inventing database dates', () => {
  const items = [
    role({ company: 'PeopleStrong', role: 'Current', start_date: '2024-04-01', end_date: null, is_current: true, date_label: 'Apr 2024 — Present' }),
    role({ company: 'CoCubes.com', role: 'Senior Software Engineer', start_date: null, end_date: null, date_label: '2014 — 15' }),
    role({ company: 'Altran', role: 'Software Engineer', start_date: '2010-01-01', end_date: '2012-04-01' }),
    role({ company: 'CoCubes.com', role: 'Software Engineer', start_date: null, end_date: null, date_label: '2012 — 14' }),
  ]
  expect(sortCareerHistory(items).map(item => item.role)).toEqual([
    'Software Engineer',
    'Software Engineer',
    'Senior Software Engineer',
    'Current',
  ])
  expect(items[1].start_date).toBeNull()
  const { container } = render(<CandidateCareerTimeline items={items} />)
  expect([...container.querySelectorAll('.career-period small')].map(el => el.textContent)).toEqual(['2010', '2012', '2014', '2024'])
  expect(container.querySelector('.career-present-end')).toHaveTextContent('Present')
})
it('keeps a year-only current role current without creating a January date', () => {
  const item = role({ start_date: null, end_date: null, is_current: true, date_label: '2024 — Present' })
  const { container } = render(<CandidateCareerTimeline items={[item]} />)
  expect(container.querySelector('.career-period small')).toHaveTextContent('2024')
  expect(container.querySelector('.career-present-end')).toHaveTextContent('Present')
})
it('uses month precision for same-year roles and proportional candidate spans', () => {
  const items = [
    role({ company: 'Example', role: 'Engineer', start_date: '2021-01-01', end_date: '2021-06-01' }),
    role({ company: 'Example', role: 'Lead', start_date: '2021-06-01', end_date: '2024-06-01' }),
  ]
  const { container } = render(<CandidateCareerTimeline items={items} />)
  expect([...container.querySelectorAll('.career-period small')].map(el => el.textContent)).toEqual(['Jan 2021', 'Jun 2021'])
  expect([...container.querySelectorAll<HTMLElement>('.career-sequence')].map(el => el.style.getPropertyValue('--career-role-span'))).toEqual(['180px', '216px'])
  expect(container.querySelector('.career-role-summary')).toHaveTextContent('Example')
  expect(container.querySelector('.career-role-summary')).toHaveTextContent('Engineer')
})
it('keeps long fictional employer, role and month-year labels visible in the profile timeline', () => {
  const item = role({
    company: 'Northstar Applied Research and Technology Cooperative',
    role: 'Machine Learning Platform Engineering Internship Lead',
    start_date: '2026-01-01',
    end_date: '2026-09-01',
  })
  const { container } = render(<CandidateCareerTimeline items={[item]} />)
  const summary = container.querySelector('.career-role-summary')
  expect(summary).toHaveTextContent('Northstar Applied Research and Technology Cooperative')
  expect(summary).toHaveTextContent('Machine Learning Platform Engineering Internship Lead')
  expect(summary).toHaveTextContent('Jan 2026 — Sep 2026')
})
it('renders recalled researcher and writer roles while keeping the career break out of employment', () => {
  const items = [
    role({ company: 'Quartz Product Studio', role: 'UX Researcher', start_date: '2017-03-01', end_date: '2020-11-01', date_label: 'March 2017 — November 2020' }),
    role({ company: 'Violet API Works', role: 'Technical Writer', start_date: null, end_date: '2020-06-01', date_label: 'Unknown — June 2020' }),
    role({ company: 'Willow Developer Tools', role: 'Senior Technical Writer', start_date: '2020-08-01', end_date: null, is_current: true, date_label: 'August 2020 — Present' }),
  ]
  const { container } = render(<CandidateCareerTimeline items={items} />)
  expect(container.querySelectorAll('.career-period')).toHaveLength(3)
  expect(screen.getByRole('button', { name: /UX Researcher at Quartz Product Studio/ })).toBeVisible()
  expect(screen.getByRole('button', { name: /Technical Writer at Violet API Works/ })).toBeVisible()
  expect(screen.getByRole('button', { name: /Senior Technical Writer at Willow Developer Tools/ })).toBeVisible()
  expect(screen.queryByRole('button', { name: /Career break at/ })).toBeNull()
  expect([...container.querySelectorAll('.career-period small')].map(el => el.textContent)).toContain('Date unknown')
  expect(container.querySelector('.career-present-end')).toHaveTextContent('Present')
})
it('shows a supported year-only start in the shared career journey', () => {
  const item = role({ start_date: null, end_date: null, date_label: '2012 — 14' })
  const { container } = render(<CareerJourney items={[item]} />)
  expect(container.querySelector('.career-period small span')).toHaveTextContent('2012')
})
it('retains every role, promotion, overlap, gap, unknown date and keyboard details', () => {
  const items = [role({ role: 'Unknown dates', start_date: null, end_date: null }), role({ role: 'Lead', start_date: '2018-08-01', end_date: '2020-01-01' }), role(), role({ company: 'Next', role: 'Current', start_date: '2021-05-01', end_date: null, gap_reason: 'Study break' })]
  const { container } = render(<CandidateCareerTimeline items={items} />)
  expect(container.querySelectorAll('.career-period')).toHaveLength(4)
  expect(container.querySelectorAll('.career-laptop')).toHaveLength(4)
  expect([...container.querySelectorAll('.career-period small')].map(el => el.textContent)).toEqual(['Mar 2018', 'Aug 2018', '2021', 'Date unknown'])
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
