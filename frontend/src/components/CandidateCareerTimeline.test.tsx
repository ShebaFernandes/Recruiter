import '@testing-library/jest-dom/vitest'
import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, expect, it } from 'vitest'
import type { WorkExperience } from '../types'
import CandidateCareerTimeline from './CandidateCareerTimeline'
import CareerJourney from './CareerJourney'
import { sortCareerHistory } from '../careerHistory'

afterEach(cleanup)
const role = (overrides:Partial<WorkExperience> = {}):WorkExperience => ({ company:'Example', role:'Engineer', start_date:'2018-03-01', end_date:'2019-01-01', description:'Built reliable tools.', gap_reason:'', confidence_status:'candidate_confirmed', ...overrides })
it.each([CareerJourney, CandidateCareerTimeline])('shows years and markers until a role is focused', Component => {
  const { container } = render(<Component items={[role()]} />)
  expect(container.querySelector('.career-journey')).toHaveTextContent('2018')
  expect(container.querySelector('.career-role-summary')).toBeNull()
  expect(screen.queryByRole('tooltip')).toBeNull()
  const marker = screen.getByRole('button', { name:/Engineer at Example/ })
  fireEvent.focus(marker)
  expect(screen.getByRole('tooltip')).toHaveTextContent('Example')
  expect(screen.getByRole('tooltip')).toHaveTextContent('Engineer')
  expect(screen.getByRole('tooltip')).toHaveTextContent('Mar 2018 — Jan 2019')
  expect(screen.getByRole('tooltip')).toHaveTextContent('Built reliable tools.')
  expect(marker).toHaveAttribute('aria-expanded', 'true')
  fireEvent.keyDown(document, { key:'Escape' })
  expect(screen.queryByRole('tooltip')).toBeNull()
})
it('preserves year-only roles and current dates without inventing January', () => {
  const items = [role({ start_date:'2024-04-01', end_date:null, is_current:true }), role({ start_date:null, end_date:null, date_label:'2014 — 15' }), role({ start_date:'2010-01-01' })]
  expect(sortCareerHistory(items).map(item => item.start_date)).toEqual(['2010-01-01', null, '2024-04-01'])
  const { container } = render(<CareerJourney items={items} />)
  expect([...container.querySelectorAll('.career-period small')].map(el => el.textContent)).toEqual(['2010','2014','2024'])
  fireEvent.focus(screen.getByRole('button', { name:/2014 — 15/ }))
  expect(screen.getByRole('tooltip')).toHaveTextContent('Dates incomplete')
  expect(screen.getByRole('tooltip')).not.toHaveTextContent('Jan')
  fireEvent.focus(screen.getByRole('button', { name:/Apr 2024 — Present/ }))
  expect(screen.getByRole('tooltip')).toHaveTextContent('Present')
})
it('positions promotions using actual dates while all default labels remain years', () => {
  const { container } = render(<CareerJourney items={[role({ start_date:'2021-01-01', end_date:'2021-06-01' }), role({ role:'Lead', start_date:'2021-06-01', end_date:'2024-06-01' })]} />)
  expect([...container.querySelectorAll('.career-period small')].map(el => el.textContent)).toEqual(['2021','2021'])
  const spans = [...container.querySelectorAll<HTMLElement>('.career-sequence')].map(el => parseFloat(el.style.getPropertyValue('--career-role-span')))
  expect(spans[0]).toBeCloseTo(64)
  expect(spans[1] / spans[0]).toBeCloseTo(36 / 5)
  fireEvent.focus(screen.getByRole('button', { name:/Lead at/ }))
  expect(screen.getByRole('tooltip')).toHaveTextContent('Career progression from Engineer')
})
it('keeps complete employer/title/date/type details in the interactive card', () => {
  const item = role({ company:'Northstar Applied Research and Technology Cooperative', role:'Senior Applied Research and Platform Engineering Lead', employment_type:'Full-time' })
  const { container } = render(<CareerJourney items={[item]} detailed />)
  expect(container.querySelector('.career-role-summary')).toHaveTextContent(item.company)
  fireEvent.mouseEnter(screen.getByRole('button'))
  expect(screen.getByRole('tooltip')).toHaveTextContent(item.company)
  expect(screen.getByRole('tooltip')).toHaveTextContent(item.role)
  expect(screen.getByRole('tooltip')).toHaveTextContent('Full-time')
})
it('keeps simultaneous overlaps as separate reachable markers at the same date coordinate', () => {
  const { container } = render(<CareerJourney items={[role(), role({ role:'Advisor', company:'Second employer' })]} />)
  const rows = [...container.querySelectorAll<HTMLElement>('.career-sequence')]
  expect(rows).toHaveLength(2)
  expect(rows[0].style.left).toEqual(rows[1].style.left)
  expect(rows[0].style.getPropertyValue('--career-marker-lane')).not.toEqual(rows[1].style.getPropertyValue('--career-marker-lane'))
  fireEvent.click(screen.getByRole('button', { name:/Advisor at/ }))
  expect(screen.getByRole('tooltip')).toHaveTextContent('Overlapping employment')
})
it('shows internship status only with evidence and keeps incidental mentions out of classification', () => {
  const { container } = render(<CareerJourney items={[role({ role:'Engineering Intern' }), role({ role:'Internship Program Manager', start_date:'2020-01-01' })]} />)
  expect(container.querySelectorAll('.is-internship')).toHaveLength(1)
  fireEvent.focus(screen.getByRole('button', { name:/Engineering Intern at/ }))
  expect(screen.getByRole('tooltip')).toHaveTextContent('Internship')
})
it('does not infer current employment or gaps from missing dates', () => {
  render(<CareerJourney items={[role({ end_date:null }), role({ start_date:null, end_date:null })]} />)
  expect(screen.queryByRole('button', { name:/Career gap/ })).toBeNull()
  fireEvent.focus(screen.getByRole('button', { name:/Start not specified/ }))
  expect(screen.getByRole('tooltip')).not.toHaveTextContent('Present')
})
it('preserves partial current dates even if a legacy record contains normalized January', () => {
  render(<CareerJourney items={[role({ start_date:'2020-01-01', end_date:null, date_label:'2020 — Present', is_current:true })]} />)
  fireEvent.focus(screen.getByRole('button'))
  expect(screen.getByRole('tooltip')).toHaveTextContent('2020 — Present')
  expect(screen.getByRole('tooltip')).not.toHaveTextContent('Jan')
})
it('never invents a gap inside a long overlap or between back-to-back months', () => {
  const { rerender } = render(<CareerJourney items={[role({ start_date:'2018-01-01', end_date:null, is_current:true }), role({ start_date:'2021-01-01', end_date:'2022-01-01' })]} />)
  expect(screen.queryByRole('button', { name:/Career gap/ })).toBeNull()
  rerender(<CareerJourney items={[role({ start_date:'2020-01-01', end_date:'2020-07-01' }), role({ start_date:'2020-08-01', end_date:'2021-12-01' }), role({ start_date:'2022-01-01', end_date:null, is_current:true })]} />)
  expect(screen.queryByRole('button', { name:/Career gap/ })).toBeNull()
})
it('reveals genuine gap details only on interaction', () => {
  const { container } = render(<CareerJourney items={[role({ end_date:'2019-01-01' }), role({ start_date:'2021-01-01', end_date:'2022-01-01', gap_reason:'Study break' })]} />)
  expect(container.querySelector('.career-journey')).not.toHaveTextContent('gap')
  fireEvent.click(screen.getByRole('button', { name:/Career gap/ }))
  expect(screen.getByRole('tooltip')).toHaveTextContent('Study break')
})
