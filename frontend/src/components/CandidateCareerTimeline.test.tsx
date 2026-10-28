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
  expect(marker).toHaveAttribute('aria-expanded', 'true')
  fireEvent.keyDown(document, { key:'Escape' })
  expect(screen.queryByRole('tooltip')).toBeNull()
})
it('preserves year-only roles and current dates without inventing January', () => {
  const items = [role({ start_date:'2024-04-01', end_date:null, is_current:true }), role({ start_date:null, end_date:null, date_label:'2014 — 15' }), role({ start_date:'2010-01-01' })]
  expect(sortCareerHistory(items).map(item => item.start_date)).toEqual(['2010-01-01', null, '2024-04-01'])
  const { container } = render(<CareerJourney items={items} />)
  expect([...container.querySelectorAll('.career-period small')].map(el => el.textContent)).toEqual(['2010','2024'])
  fireEvent.focus(screen.getByRole('button', { name:/2014 — 15/ }))
  expect(screen.getByRole('tooltip')).toHaveTextContent('Dates incomplete')
  expect(screen.getByRole('tooltip')).not.toHaveTextContent('Jan')
  fireEvent.focus(screen.getByRole('button', { name:/Apr 2024 — Present/ }))
  expect(screen.getByRole('tooltip')).toHaveTextContent('Present')
})
it('positions promotions using actual dates while all default labels remain years', () => {
  const { container } = render(<CareerJourney items={[role({ start_date:'2021-01-01', end_date:'2021-06-01' }), role({ role:'Lead', start_date:'2021-06-01', end_date:'2024-06-01' })]} />)
  expect([...container.querySelectorAll('.career-period small')].map(el => el.textContent)).toEqual(['2021'])
  const spans = [...container.querySelectorAll<HTMLElement>('.career-sequence')].map(el => parseFloat(el.style.getPropertyValue('--career-role-span')))
  expect(spans[0]).toBeGreaterThan(0)
  expect(spans[1] / spans[0]).toBeCloseTo(36 / 5, 0)
  fireEvent.focus(screen.getByRole('button', { name:/Lead at/ }))
  expect(screen.getByRole('tooltip')).toHaveTextContent('Career progression from Engineer')
})
it('keeps complete employer/title/date/type details in the interactive card', () => {
  const item = role({ company:'Northstar Applied Research and Technology Cooperative', role:'Senior Applied Research and Platform Engineering Lead', employment_type:'Full-time' })
  const { container } = render(<CareerJourney items={[item]} detailed />)
  expect(container.querySelector('.career-role-summary')).toBeNull()
  fireEvent.mouseEnter(screen.getByRole('button'))
  expect(screen.getByRole('tooltip')).toHaveTextContent(item.company)
  expect(screen.getByRole('tooltip')).toHaveTextContent(item.role)
  expect(screen.getByRole('tooltip')).toHaveTextContent('Full-time')
})
it('keeps simultaneous overlaps as separate roles in one accessible cluster', () => {
  const { container } = render(<CareerJourney items={[role(), role({ role:'Advisor', company:'Second employer' })]} />)
  const rows = [...container.querySelectorAll<HTMLElement>('.career-sequence')]
  expect(rows).toHaveLength(2)
  expect(rows[0].style.left).toEqual(rows[1].style.left)
  expect(container.querySelectorAll('.career-period .career-job')).toHaveLength(1)
  fireEvent.click(screen.getByRole('button', { name:/2 roles grouped here/ }))
  expect(screen.getByRole('dialog')).toHaveTextContent('Example')
  expect(screen.getByRole('dialog')).toHaveTextContent('Second employer')
  expect(screen.getByRole('dialog')).toHaveTextContent('Overlapping employment')
})
it('shows internship status only with evidence and keeps incidental mentions out of classification', () => {
  const { container } = render(<CareerJourney items={[role({ role:'Engineering Intern' }), role({ role:'Internship Program Manager', start_date:'2020-01-01' })]} />)
  expect(container.querySelectorAll('.is-internship')).toHaveLength(1)
  fireEvent.focus(screen.getByRole('button', { name:/Engineering Intern at/ }))
  expect(screen.getByRole('tooltip')).toHaveTextContent('Internship')
})
it('does not infer current employment or gaps from missing dates', () => {
  const { container } = render(<CareerJourney items={[role({ end_date:null }), role({ start_date:null, end_date:null })]} />)
  expect(screen.queryByRole('button', { name:/Career gap/ })).toBeNull()
  expect(container.querySelectorAll('.career-sequence.dates-incomplete')).toHaveLength(1)
  fireEvent.focus(screen.getByRole('button', { name:/Start not specified/ }))
  expect(screen.getByRole('tooltip')).not.toHaveTextContent('Present')
})
it('does not draw a dated axis for only undated employment', () => {
  const { container } = render(<CareerJourney items={[role({ start_date:null, end_date:null, date_label:'2014 — 15' })]} />)
  expect(container.querySelector('.career-axis')).toBeNull()
  expect(screen.getByRole('button', { name:/Engineer at Example/ })).toBeVisible()
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
it('shows only legend categories represented by saved roles and genuine gaps', () => {
  const intern = role({ id:1, role:'Engineering Intern', employment_type:'Internship', start_date:'2018-01-01', end_date:'2018-08-01' })
  const employee = role({ id:2, role:'Engineer', employment_type:'Full-time', start_date:'2018-09-01', end_date:'2019-01-01' })
  const older = role({ id:3, role:'Lead', employment_type:'Full-time', start_date:'2021-01-01', end_date:'2022-01-01' })
  const extraction = { resume_id:1, status:'verified_ai' as const, source:'ai' as const, reason_code:'', profile_state:'applied' as const, stale_profile_preserved:false, accepted_role_count:2, saved_role_count:3, verified_role_ids:[1, 2], unverified_role_ids:[3] }
  const { rerender } = render(<CareerJourney items={[intern]} extraction={extraction} />)
  expect(screen.getByLabelText('Career journey legend')).toHaveTextContent('Internship')
  expect(screen.getByLabelText('Career journey legend')).not.toHaveTextContent('Employment')
  expect(screen.getByLabelText('Career journey legend')).not.toHaveTextContent('Career gap')
  expect(screen.getByLabelText('Career journey legend')).not.toHaveTextContent('Unverified history')
  rerender(<CareerJourney items={[intern, employee, older]} extraction={extraction} />)
  expect(screen.getByLabelText('Career journey legend')).toHaveTextContent('Employment')
  expect(screen.getByLabelText('Career journey legend')).toHaveTextContent('Internship')
  expect(screen.getByLabelText('Career journey legend')).toHaveTextContent('Career gap')
  expect(screen.getByLabelText('Career journey legend')).toHaveTextContent('Unverified history')
  expect(screen.getByRole('button', { name:/Lead at/ }).closest('.career-sequence')).toHaveClass('needs-review')
})
