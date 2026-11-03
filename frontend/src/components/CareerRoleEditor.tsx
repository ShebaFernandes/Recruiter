import { useEffect, useRef, useState, type FormEvent } from 'react'
import type { WorkExperience, CareerRolePatch } from '../types'
import { roleDateInput, yearMonthValue } from './careerRoleDates'
import { ongoing } from './careerTimelineLayout'

export default function CareerRoleEditor({ item, busy, save, cancel, focusField }: {
  item: WorkExperience
  busy: boolean
  save: (patch: CareerRolePatch) => Promise<boolean>
  cancel: () => void
  focusField?: string
}) {
  const form = useRef<HTMLFormElement>(null)
  const initialStart = roleDateInput(item, 'start')
  const initialEnd = roleDateInput(item, 'end')
  const [company, setCompany] = useState(item.company)
  const [role, setRole] = useState(item.role)
  const [startMonth, setStartMonth] = useState(initialStart.month)
  const [startYear, setStartYear] = useState(initialStart.year)
  const [startYearOnly, setStartYearOnly] = useState(initialStart.yearOnly)
  const [endMonth, setEndMonth] = useState(initialEnd.month)
  const [endYear, setEndYear] = useState(initialEnd.year)
  const [endYearOnly, setEndYearOnly] = useState(initialEnd.yearOnly)
  const [current, setCurrent] = useState(ongoing(item))
  const [startTouched, setStartTouched] = useState(false)
  const [endTouched, setEndTouched] = useState(false)
  const [currentTouched, setCurrentTouched] = useState(false)
  const [saveError, setSaveError] = useState(false)
  useEffect(() => {
    const name = focusField || 'company'
    form.current?.querySelector<HTMLInputElement>(`[name="${name}"]`)?.focus()
    form.current?.scrollIntoView?.({ block:'nearest' })
  }, [focusField])
  const dirty = company.trim() !== item.company || role.trim() !== item.role || startTouched || endTouched || currentTouched
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const patch: CareerRolePatch = {}
    if (company.trim() !== item.company) patch.company = company.trim()
    if (role.trim() !== item.role) patch.role = role.trim()
    if (startTouched) patch.start = yearMonthValue(startMonth, startYear, startYearOnly)
    if (endTouched && !current) patch.end = yearMonthValue(endMonth, endYear, endYearOnly)
    if (currentTouched) patch.is_current = current
    if (Object.keys(patch).length) setSaveError(!await save(patch))
  }
  return <form ref={form} className="cp-career-inline-editor" onSubmit={event => void submit(event)} aria-label={`Edit ${item.role || 'role'} at ${item.company || 'unspecified employer'}`}>
    <div className="cp-career-inline-heading"><strong>Edit role</strong></div>
    <fieldset disabled={busy}>
      <div className="cp-career-inline-grid">
        <label>Employer<input name="company" maxLength={180} required={Boolean(item.company)} value={company} onChange={event => setCompany(event.target.value)} /></label>
        <label>Job title<input name="role" maxLength={180} required={Boolean(item.role)} value={role} onChange={event => setRole(event.target.value)} /></label>
        <div className="cp-career-date-field"><label htmlFor="career-start-date">Start date</label>{startYearOnly
          ? <input id="career-start-date" name="start" type="number" min="1900" max="2100" inputMode="numeric" placeholder="Year" value={startYear} onChange={event => { setStartYear(event.target.value); setStartTouched(true) }} />
          : <input id="career-start-date" name="start" type="month" value={startMonth} onChange={event => { setStartMonth(event.target.value); setStartYear(event.target.value.slice(0, 4)); setStartTouched(true) }} />}
          {(!startMonth || startYearOnly) && <label className="cp-career-month-unknown"><input type="checkbox" checked={startYearOnly} onChange={event => { setStartYearOnly(event.target.checked); setStartTouched(true) }} />I don't remember the month</label>}
        </div>
        <div className="cp-career-date-field"><label htmlFor="career-end-date">End date</label>{current ? <span className="cp-career-current-note">Present</span> : endYearOnly
          ? <input id="career-end-date" name="end" type="number" min="1900" max="2100" inputMode="numeric" placeholder="Year" value={endYear} onChange={event => { setEndYear(event.target.value); setEndTouched(true) }} />
          : <input id="career-end-date" name="end" type="month" value={endMonth} onChange={event => { setEndMonth(event.target.value); setEndYear(event.target.value.slice(0, 4)); setEndTouched(true) }} />}
          {!current && (!endMonth || endYearOnly) && <label className="cp-career-month-unknown"><input type="checkbox" checked={endYearOnly} onChange={event => { setEndYearOnly(event.target.checked); setEndTouched(true) }} />I don't remember the month</label>}
          <label className="cp-career-current"><input type="checkbox" checked={current} onChange={event => { setCurrent(event.target.checked); setCurrentTouched(true) }} />I still work here</label>
        </div>
      </div>
      {saveError && <p role="alert">Changes were not saved. Check the details and try again.</p>}
      <div className="cp-career-inline-actions"><button type="button" onClick={cancel}>Cancel</button><button className="primary" type="submit" disabled={!dirty || busy}>Save</button></div>
    </fieldset>
  </form>
}
