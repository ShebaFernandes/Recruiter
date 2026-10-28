import { useEffect, useId, useRef, useState, type CSSProperties } from 'react'
import { createPortal } from 'react-dom'
import type { EmploymentExtraction, WorkExperience } from '../types'
import { sortCareerHistory } from '../careerHistory'
import { CandidateMilestoneIcon } from './CandidateMilestoneIcon'
import { coarseDates, endTime, fittedCareerTimeline, isInternship, ongoing, time } from './careerTimelineLayout'
import EmploymentHistoryStatus from './EmploymentHistoryStatus'
import './career-journey.css'

// Compact recruiter lists can omit summaries; profile views retain saved role labels.
type CareerJourneyProps = { items: WorkExperience[]; detailed?: boolean; showCompanyLabels?: boolean; compactMarkers?: boolean; profilePresentation?: boolean; minimal?: boolean; reverse?: boolean; presentAtEnd?: boolean; candidateMilestones?: boolean; extraction?: EmploymentExtraction | null; identityWarning?: string | null; onEditRole?: (item: WorkExperience) => void; showStatus?: boolean }
type Detail = { key:string; company?:string; title:string; period:string; employment?:string; verification?:string; note?:string; description?:string; roles?:Detail[]; item?:WorkExperience }
type OpenDetail = Detail & { x:number; y:number; maxHeight:number }
const monthNames = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
const monthYear = (value:string | null) => {
  const matched = value?.match(/^((?:19|20)\d{2})-(0[1-9]|1[0-2])(?:-|$)/)
  return matched ? `${monthNames[Number(matched[2]) - 1]} ${matched[1]}` : value || ''
}
function period(item:WorkExperience) {
  if (item.date_label && (coarseDates(item) || !item.start_date || (!item.end_date && !ongoing(item)))) return item.date_label
  return `${monthYear(item.start_date) || 'Start not specified'} — ${monthYear(item.end_date) || (ongoing(item) ? 'Present' : 'End not specified')}`
}
function employment(item:WorkExperience) {
  if (isInternship(item)) return 'Internship'
  // Neither a long duration nor the absence of an internship label proves full-time work.
  if (['supported', 'candidate_confirmed'].includes(item.confidence_status || '') && item.employment_type) return item.employment_type
  return ''
}
function gapBefore(items:WorkExperience[], index:number, now:number) {
  const item = items[index]
  const start = time(item.start_date)
  const earlier = items.slice(0, index).filter(row => Number.isFinite(time(row.start_date)))
  const uncertain = items.some(row => !Number.isFinite(time(row.start_date)) || coarseDates(row)) || earlier.some(row => !Number.isFinite(endTime(row, now)))
  const latestEnd = Math.max(...earlier.map(row => endTime(row, now)).filter(Number.isFinite))
  const gapStart = Number.isFinite(latestEnd) ? Date.UTC(new Date(latestEnd).getUTCFullYear(), new Date(latestEnd).getUTCMonth() + 1, 1) : NaN
  const months = !uncertain && start - gapStart >= 28 * 86400000 ? Math.round((start - gapStart) / 2629800000) : 0
  return { months, gapStart }
}

/** No example history or fetching: every marker represents a supplied saved record. */
export default function CareerJourney({ items, extraction, identityWarning, onEditRole, showStatus = true }: CareerJourneyProps) {
  const sorted = sortCareerHistory(items)
  const [now] = useState(Date.now)
  const id = useId()
  const root = useRef<HTMLDivElement>(null)
  const [viewportWidth, setViewportWidth] = useState(0)
  useEffect(() => {
    if (!root.current || typeof ResizeObserver === 'undefined') return
    const observer = new ResizeObserver(entries => setViewportWidth(entries[0].target.clientWidth))
    observer.observe(root.current)
    return () => observer.disconnect()
  }, [items.length])
  const layout = fittedCareerTimeline(sorted, viewportWidth || 720, now)
  const [active, setActive] = useState<OpenDetail | null>(null)
  const pinned = useRef<string | null>(null)
  const trigger = useRef<HTMLElement | null>(null)
  const suppressFocus = useRef(false)
  const hideTimer = useRef<ReturnType<typeof setTimeout> | undefined>(undefined)
  const close = (restoreFocus = false) => { clearTimeout(hideTimer.current); pinned.current = null; setActive(null); if (restoreFocus) { suppressFocus.current = true; trigger.current?.focus(); suppressFocus.current = false } }
  const leave = () => { if (pinned.current !== active?.key) hideTimer.current = setTimeout(close, 180) }
  useEffect(() => {
    const dismiss = (event:Event) => {
      if (event.type === 'keydown') {
        if ((event as KeyboardEvent).key === 'Escape') close(true)
        return
      }
      const target = event.target instanceof Element ? event.target : null
      if (target?.closest('.career-popover')) return
      if (event.type === 'pointerdown' && root.current?.contains(event.target as Node)) return
      close()
    }
    document.addEventListener('keydown', dismiss)
    document.addEventListener('pointerdown', dismiss)
    window.addEventListener('resize', dismiss)
    window.addEventListener('wheel', dismiss, { passive:true }); window.addEventListener('touchmove', dismiss, { passive:true })
    return () => { clearTimeout(hideTimer.current); document.removeEventListener('keydown', dismiss); document.removeEventListener('pointerdown', dismiss); window.removeEventListener('resize', dismiss); window.removeEventListener('wheel', dismiss); window.removeEventListener('touchmove', dismiss) }
  }, [])
  const show = (element:HTMLElement, data:Detail) => {
    clearTimeout(hideTimer.current)
    trigger.current = element
    if (pinned.current !== data.key) pinned.current = null
    const box = element.getBoundingClientRect()
    const width = Math.min(320, window.innerWidth - 24)
    const preferredHeight = Math.min(data.roles ? 320 : 260, window.innerHeight * .7)
    const below = window.innerHeight - box.bottom - 22
    const above = box.top - 22
    const placeAbove = below < preferredHeight && above > below
    const maxHeight = Math.min(preferredHeight, Math.max(80, placeAbove ? above : below))
    const y = placeAbove ? box.top - maxHeight - 10 : box.bottom + 10
    setActive({ ...data, x:Math.max(12, Math.min(box.left - width / 2 + box.width / 2, window.innerWidth - width - 12)), y:Math.max(12, y), maxHeight })
  }
  const handlers = (data:Detail) => ({
    onMouseEnter: (event:React.MouseEvent<HTMLButtonElement>) => { if (event.buttons === 0) show(event.currentTarget, data) },
    onMouseLeave: leave,
    onFocus: (event:React.FocusEvent<HTMLButtonElement>) => { if (!suppressFocus.current) show(event.currentTarget, data) },
    onBlur: (event:React.FocusEvent<HTMLButtonElement>) => { if (pinned.current !== data.key && !(event.relatedTarget as HTMLElement | null)?.closest('.career-popover')) close() },
    onClick: (event:React.MouseEvent<HTMLButtonElement>) => { if (pinned.current === data.key) close(); else { pinned.current = data.key; show(event.currentTarget, data); if (data.roles) window.setTimeout(() => document.getElementById(id)?.focus(), 0); else if (event.detail === 0) window.setTimeout(() => document.getElementById(id)?.querySelector<HTMLElement>('.career-popover-edit')?.focus(), 0) } },
  })
  const verified = new Set(extraction?.verified_role_ids || [])
  const gaps = sorted.map((_, index) => gapBefore(sorted, index, now))
  const hasVerifiedInternship = sorted.some(item => item.id != null && verified.has(item.id) && isInternship(item))
  const hasVerifiedEmployment = sorted.some(item => item.id != null && verified.has(item.id) && !isInternship(item))
  const hasUnverified = sorted.some(item => item.id == null || !verified.has(item.id))
  const hasGap = gaps.some(gap => gap.months > 0)
  const details = sorted.map((item, index):Detail => {
    const earlier = sorted.slice(0, index).filter(row => Number.isFinite(time(row.start_date)))
    const start = time(item.start_date)
    const overlaps = !coarseDates(item) && earlier.some(row => !coarseDates(row) && endTime(row, now) > start)
    const previousRole = sorted.slice(0, index).reverse().find(row => row.company.trim().toLowerCase() === item.company.trim().toLowerCase() && row.role !== item.role)
    const isVerified = item.id != null && verified.has(item.id)
    const confirmation = item.confidence_status === 'candidate_confirmed' ? 'Candidate-confirmed history. ' : ''
    const verification = isVerified ? '' : `${confirmation}Not matched to the latest resume.`
    return { key:`${item.id ?? index}-${item.company}-${item.start_date}`, item, company:item.company || 'Employer not specified', title:item.role || 'Role not specified', period:period(item), employment:employment(item), verification,
      note:[overlaps ? 'Overlapping employment' : '', previousRole ? `Career progression from ${previousRole.role}` : '', !layout.positions[index].dated ? 'Dates incomplete · not placed on the calendar scale' : ''].filter(Boolean).join(' · ') }
  })
  const groups = new Map(layout.groups.map(group => [group.members[0], group]))
  const showEndYear = layout.endYear !== null && !layout.yearLabels.includes(String(layout.endYear))
  return <div className="career-history">
    {showStatus && <EmploymentHistoryStatus items={items} extraction={extraction} identityWarning={identityWarning} />}
    {items.length > 0 && <>
      <div ref={root} className="career-journey shared calendar-timeline marker-only" aria-label="Career journey" role="list">
        <div className="career-calendar" role="presentation" style={{ height:layout.height }}>
          {layout.hasDated && <span className={`career-axis ${sorted.some(item => ongoing(item) && Number.isFinite(time(item.start_date)) && !coarseDates(item)) ? 'is-current' : ''}`} aria-hidden="true" style={{ top:layout.axisY }} />}
          {sorted.map((item, index) => {
            const position = layout.positions[index]
            const { months:gap, gapStart } = gaps[index]
            const start = time(item.start_date)
            const isVerified = item.id != null && verified.has(item.id)
            const data = details[index]
            const group = groups.get(index)
            const memberDetails = group?.members.map(member => details[member]) || []
            const clustered = memberDetails.length > 1
            const groupHasInternship = group?.members.some(member => isInternship(sorted[member])) || false
            const groupMixedInternship = groupHasInternship && group?.members.some(member => !isInternship(sorted[member]))
            const groupUnverified = group?.members.some(member => sorted[member].id == null || !verified.has(sorted[member].id!))
            const markerData:Detail = clustered ? { key:`cluster-${memberDetails.map(role => role.key).join(':')}`, title:`${memberDetails.length} roles grouped here`, period:'', roles:memberDetails } : data
            return <div className={`career-sequence ${isInternship(item) ? 'is-internship' : ''} ${isVerified ? 'is-verified' : 'needs-review'} ${position.dated ? '' : 'dates-incomplete'} ${groupMixedInternship ? 'is-cluster-mixed' : ''} ${groupUnverified ? 'cluster-needs-review' : ''}`} key={data.key}
              style={{ left:position.x, top:layout.axisY - 22, '--career-role-span':`${position.span}px` } as CSSProperties}>
              <span className="career-period-line" aria-hidden="true" />
              {gap > 0 && <div className="career-gap-period" role="listitem" style={{ left:layout.dateX(gapStart) - position.x, top:0, width:layout.dateX(start) - layout.dateX(gapStart) }}>
                <button type="button" className="career-job career-gap-marker" aria-label={`Career gap of approximately ${gap} ${gap === 1 ? 'month' : 'months'}`} aria-expanded={active?.key === `${data.key}-gap`} aria-describedby={active?.key === `${data.key}-gap` ? id : undefined} {...handlers({ key:`${data.key}-gap`, title:'Career gap', period:`Approximately ${gap} ${gap === 1 ? 'month' : 'months'}`, description:item.gap_reason || 'Reason not provided by the candidate.' })}><span className="career-gap-line" aria-hidden="true" /></button>
              </div>}
              {group && <div className="career-period" role="listitem">
                <button type="button" className={`career-job ${clustered ? 'is-cluster' : ''} ${active?.key === markerData.key ? 'is-active' : ''}`} style={{ left:group.x - position.x - 22 }} aria-label={clustered ? `${memberDetails.length} roles grouped here. Open for details.` : `${data.title} at ${data.company}, ${data.period}${data.employment ? `, ${data.employment}` : ''}${data.note?.includes('Overlapping') ? ', overlapping employment' : ''}${data.verification ? `, ${data.verification}` : ''}`} aria-expanded={active?.key === markerData.key} aria-haspopup={clustered ? 'dialog' : undefined} aria-controls={clustered ? id : undefined} aria-describedby={!clustered && active?.key === markerData.key ? id : undefined} {...handlers(markerData)}>
                  <span className="career-marker-icon" aria-hidden="true">{clustered ? <span className="career-cluster-count">{memberDetails.length}</span> : <CandidateMilestoneIcon />}</span>
                  {layout.yearLabels[index] && <small>{layout.yearLabels[index]}</small>}
                </button>
              </div>}
            </div>
          })}
          {showEndYear && <span className="career-end-year" style={{ right:24, top:layout.axisY + 24 }} aria-hidden="true">{layout.endYear}</span>}
        </div>
      </div>
      <div className="career-legend" aria-label="Career journey legend">
        {hasVerifiedEmployment && <span><i className="career-legend-marker is-employment" aria-hidden="true" />Employment</span>}
        {hasVerifiedInternship && <span><i className="career-legend-marker is-internship" aria-hidden="true" />Internship</span>}
        {hasGap && <span><i className="career-legend-gap" aria-hidden="true" />Career gap</span>}
        {hasUnverified && <span><i className="career-legend-marker is-unverified" aria-hidden="true" />Unverified history</span>}
      </div>
    </>}
    {active && createPortal(<div id={id} className={`career-popover ${active.roles ? 'career-cluster-popover' : ''}`} role={active.roles ? 'dialog' : 'tooltip'} aria-label={active.roles ? `${active.roles.length} roles grouped here` : undefined} tabIndex={active.roles ? -1 : undefined} onBlur={event => { if (active.roles && !event.currentTarget.contains(event.relatedTarget as Node)) close() }} onMouseEnter={() => clearTimeout(hideTimer.current)} onMouseLeave={leave} style={{ left:active.x, top:active.y, maxHeight:active.maxHeight }}>
      {active.roles ? <><strong>{active.roles.length} roles grouped here</strong><ul>{active.roles.map(role => <li key={role.key}><b>{role.company}</b><span>{role.title}</span><span>{role.period}</span>{role.employment && <span className="career-detail-type">{role.employment}</span>}{role.verification && <small>{role.verification}</small>}{role.note && <small>{role.note}</small>}{onEditRole && role.item?.id != null && <button type="button" className="career-popover-edit" onClick={() => { onEditRole(role.item!); close() }}>Edit this role</button>}</li>)}</ul><button type="button" className="career-cluster-close" onClick={() => close(true)}>Close role list</button></> : <>
        <strong>{active.company || active.title}</strong>{active.company && <b>{active.title}</b>}
        <span className="career-detail-dates">{active.period}</span>
        {active.employment && <span className="career-detail-type">{active.employment}</span>}
        {active.verification && <p className="career-detail-verification">{active.verification}</p>}
        {active.note && <p>{active.note}</p>}{active.description && <p>{active.description}</p>}
        {onEditRole && active.item?.id != null && <button type="button" className="career-popover-edit" onClick={() => { onEditRole(active.item!); close() }}>Edit this role</button>}
      </>}
    </div>, document.body)}
  </div>
}
