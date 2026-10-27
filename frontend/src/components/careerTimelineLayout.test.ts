import { describe, expect, it } from 'vitest'
import type { WorkExperience } from '../types'
import { careerTimelineLayout, isInternship } from './careerTimelineLayout'
const role = (overrides: Partial<WorkExperience> = {}): WorkExperience => ({ company:'Example', role:'Engineer', start_date:'2020-01-01', end_date:'2021-01-01', description:'', gap_reason:'', ...overrides })
describe('shared calendar spacing', () => {
  it('uses equal calendar units for jobs, overlaps and gaps without minimum duration distortion', () => {
    const result = careerTimelineLayout([role(), role({ start_date:'2020-07-01', end_date:'2022-01-01' }), role({ start_date:'2023-01-01', end_date:'2023-02-01' })])
    expect(result.rows.map(row => row.left)).toEqual([0, 264, 1584])
    expect(result.rows.map(row => row.span)).toEqual([528, 792, 44])
    expect(result.rows[1].barLane).not.toBe(result.rows[0].barLane)
    expect(result.rows[1].lane).toBe(result.rows[0].lane)
  })
  it('places incomplete dates outside the precise scale and keeps current roles current', () => {
    const result = careerTimelineLayout([role({ end_date:null, is_current:true }), role({ start_date:null, end_date:null, date_label:'2018 — 19' }), role({ start_date:null, end_date:null })], Date.UTC(2022,0,1))
    expect(result.rows[0].span).toBe(576)
    expect(result.rows.slice(1).every(row => !row.dated && row.span === 0 && row.left > result.datedEnd)).toBe(true)
  })
  it('requires explicit internship evidence, never short duration or incidental descriptions', () => {
    expect(isInternship(role({ role:'Software Engineering Intern' }))).toBe(true)
    expect(isInternship(role({ role:'AI Intern / SDE Intern - AI' }))).toBe(true)
    expect(isInternship(role({ role:'Software Engineer (Intern)' }))).toBe(true)
    expect(isInternship(role({ role:'International Program Manager' }))).toBe(false)
    expect(isInternship(role({ employment_type:'Internship', confidence_status:'candidate_confirmed' }))).toBe(true)
    expect(isInternship(role({ employment_type:'Internship', confidence_status:'supported' }))).toBe(true)
    expect(isInternship(role({ employment_type:'Internship' }))).toBe(false)
    expect(isInternship(role({ description:'Mentored interns', end_date:'2020-02-01' }))).toBe(false)
    expect(isInternship(role({ role:'Internship Program Manager' }))).toBe(false)
    expect(isInternship(role({ role:'Intern Manager' }))).toBe(false)
    expect(isInternship(role({ role:'Intern', employment_type:'Full-time', confidence_status:'candidate_confirmed' }))).toBe(false)
  })
})

it('gives a single dated role a readable span without changing its dates', () => {
  const item = role({ start_date:'2023-01-01', end_date:'2023-02-01' })
  const result = careerTimelineLayout([item])
  expect(result.rows[0].span).toBe(360)
  expect(item.start_date).toBe('2023-01-01')
  expect(item.end_date).toBe('2023-02-01')
  expect(careerTimelineLayout([role({ start_date:null, end_date:null })]).rows[0].span).toBe(0)
})

it('fills the stated end month and leaves only the actual intervening month as a gap', () => {
  const intern = role({ role:'AI Intern / SDE Intern - AI', start_date:'2026-01-01', end_date:'2026-07-01', date_label:'Jan 2026 - Jul 2026' })
  const employee = role({ start_date:'2026-09-01', end_date:null, is_current:true })
  const layout = careerTimelineLayout([intern, employee], Date.UTC(2026, 9, 27))
  expect(layout.rows[0].left + layout.rows[0].span).toBe(layout.x(Date.UTC(2026, 7, 1)))
  expect(layout.rows[1].left - layout.rows[0].span).toBe(layout.x(Date.UTC(2026, 1, 1)))
  expect(intern.end_date).toBe('2026-07-01')
  expect(careerTimelineLayout([{ ...intern, date_label:'2026-01-01 — 2026-07-01' }, employee], Date.UTC(2026, 9, 27)).rows[0].span).toBe(layout.x(Date.UTC(2026, 6, 1)))
})
