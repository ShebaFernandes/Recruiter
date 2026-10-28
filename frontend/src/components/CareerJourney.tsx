import { useEffect, useId, useRef, useState, type CSSProperties } from 'react'
import { createPortal } from 'react-dom'
import type { EmploymentExtraction, WorkExperience } from '../types'
import { sortCareerHistory } from '../careerHistory'
import { CandidateMilestoneIcon } from './CandidateMilestoneIcon'
import { coarseDates, endTime, fittedCareerTimeline, isInternship, ongoing, time } from './careerTimelineLayout'
import EmploymentHistoryStatus from './EmploymentHistoryStatus'
import './career-journey.css'

// Compact recruiter lists can omit summaries; profile views retain saved role labels.
type CareerJourneyProps = { items: WorkExperience[]; detailed?: boolean; showCompanyLabels?: boolean; compactMarkers?: boolean; profilePresentation?: boolean; minimal?: boolean; reverse?: boolean; presentAtEnd?: boolean; candidateMilestones?: boolean; extraction?: EmploymentExtraction | null; identityWarning?: string | null }
type Detail = { key:string; company?:string; title:string; period:string; employment?:string; verification?:string; note?:string; description?:string }
type OpenDetail = Detail & { x:number; y:number; above:boolean }
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

/** No example history or fetching: every marker represents a supplied saved record. */
export default function CareerJourney({ items, extraction, identityWarning }: CareerJourneyProps) {
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
  const hideTimer = useRef<ReturnType<typeof setTimeout> | undefined>(undefined)
  const close = () => { clearTimeout(hideTimer.current); pinned.current = null; setActive(null) }
  const leave = () => { if (pinned.current !== active?.key) hideTimer.current = setTimeout(close, 180) }
  useEffect(() => {
    const dismiss = (event:Event) => {
      if (event.type === 'keydown' && (event as KeyboardEvent).key !== 'Escape') return
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
    if (pinned.current !== data.key) pinned.current = null
    const box = element.getBoundingClientRect()
    const width = Math.min(360, window.innerWidth - 24)
    const above = window.innerHeight - box.bottom < 280 && box.top > 280
    setActive({ ...data, x:Math.max(12, Math.min(box.left - width / 2 + box.width / 2, window.innerWidth - width - 12)), y:above ? window.innerHeight - box.top + 10 : Math.max(12, Math.min(box.bottom + 10, window.innerHeight - 272)), above })
  }
  const handlers = (data:Detail) => ({
    onMouseEnter: (event:React.MouseEvent<HTMLButtonElement>) => { if (event.buttons === 0) show(event.currentTarget, data) },
    onMouseLeave: leave,
    onFocus: (event:React.FocusEvent<HTMLButtonElement>) => show(event.currentTarget, data),
    onBlur: close,
    onClick: (event:React.MouseEvent<HTMLButtonElement>) => { if (pinned.current === data.key) close(); else { pinned.current = data.key; show(event.currentTarget, data) } },
  })
  const verified = new Set(extraction?.verified_role_ids || [])
  const anyUnverified = items.some(item => item.id == null || !verified.has(item.id))
  const showEndYear = layout.endYear !== null && !layout.yearLabels.includes(String(layout.endYear))
  return <div className="career-history">
    <EmploymentHistoryStatus items={items} extraction={extraction} identityWarning={identityWarning} />
    {items.length > 0 && <>
      {anyUnverified && <p className="career-review-key">Hollow markers show older saved roles not verified against the latest resume.</p>}
      <div ref={root} className="career-journey shared calendar-timeline marker-only" aria-label="Career journey" role="list">
        <div className="career-calendar" role="presentation" style={{ height:layout.height }}>
          {layout.hasDated && <span className={`career-axis ${sorted.some(item => ongoing(item) && Number.isFinite(time(item.start_date)) && !coarseDates(item)) ? 'is-current' : ''}`} aria-hidden="true" style={{ top:layout.axisY }} />}
          {sorted.map((item, index) => {
            const position = layout.positions[index]
            const start = time(item.start_date)
            const earlier = sorted.slice(0, index).filter(row => Number.isFinite(time(row.start_date)))
            const uncertain = sorted.some(row => !Number.isFinite(time(row.start_date)) || coarseDates(row)) || earlier.some(row => !Number.isFinite(endTime(row, now)))
            const latestEnd = Math.max(...earlier.map(row => endTime(row, now)).filter(Number.isFinite))
            const gapStart = Number.isFinite(latestEnd) ? Date.UTC(new Date(latestEnd).getUTCFullYear(), new Date(latestEnd).getUTCMonth() + 1, 1) : NaN
            const gap = !uncertain && start - gapStart >= 28 * 86400000 ? Math.round((start - gapStart) / 2629800000) : 0
            const overlaps = !coarseDates(item) && earlier.some(row => !coarseDates(row) && endTime(row, now) > start)
            const previousRole = sorted.slice(0, index).reverse().find(row => row.company.trim().toLowerCase() === item.company.trim().toLowerCase() && row.role !== item.role)
            const isVerified = item.id != null && verified.has(item.id)
            const confirmation = item.confidence_status === 'candidate_confirmed' ? 'Candidate-confirmed history. ' : ''
            const verification = isVerified ? 'Matched to the latest resume.' : `${confirmation}Not matched to the latest resume.`
            const key = `${item.id ?? index}-${item.company}-${item.start_date}`
            const data:Detail = { key, company:item.company || 'Employer not specified', title:item.role || 'Role not specified', period:period(item), employment:employment(item), verification, description:item.description,
              note:[overlaps ? 'Overlapping employment' : '', previousRole ? `Career progression from ${previousRole.role}` : '', !position.dated ? 'Dates incomplete · not placed on the calendar scale' : ''].filter(Boolean).join(' · ') }
            const gapData:Detail = { key:`${key}-gap`, title:'Career gap', period:`Approximately ${gap} ${gap === 1 ? 'month' : 'months'}`, description:item.gap_reason || 'Reason not provided by the candidate.' }
            const markerTop = position.dated ? layout.axisY - position.lane * 48 - 22 : layout.unknownY + position.lane * 48 - 22
            return <div className={`career-sequence ${isInternship(item) ? 'is-internship' : ''} ${isVerified ? 'is-verified' : 'needs-review'} ${position.dated ? '' : 'dates-incomplete'}`} key={key}
              style={{ left:position.x, top:markerTop, '--career-role-span':`${position.span}px`, '--career-marker-lane':position.lane } as CSSProperties}>
              <span className="career-period-line" aria-hidden="true" />
              {gap > 0 && <div className="career-gap-period" role="listitem" style={{ left:layout.dateX(gapStart) - position.x, top:layout.axisY - markerTop - 22, width:layout.dateX(start) - layout.dateX(gapStart) }}>
                <button type="button" className="career-job career-gap-marker" aria-label={`Career gap of approximately ${gap} ${gap === 1 ? 'month' : 'months'}`} aria-expanded={active?.key === gapData.key} aria-describedby={active?.key === gapData.key ? id : undefined} {...handlers(gapData)}><span className="career-gap-line" aria-hidden="true" /></button>
              </div>}
              <div className="career-period" role="listitem">
                {position.dated && position.lane > 0 && <span className="career-marker-stem" aria-hidden="true" />}
                <button type="button" className={`career-job ${active?.key === key ? 'is-active' : ''}`} aria-label={`${data.title} at ${data.company}, ${data.period}${data.employment ? `, ${data.employment}` : ''}${overlaps ? ', overlapping employment' : ''}, ${verification}`} aria-expanded={active?.key === key} aria-describedby={active?.key === key ? id : undefined} {...handlers(data)}>
                  <span className="career-marker-icon" aria-hidden="true"><CandidateMilestoneIcon /></span>
                  {layout.yearLabels[index] && <small style={{ top:position.dated ? layout.axisY - markerTop + 25 : 47 }}>{layout.yearLabels[index]}</small>}
                </button>
              </div>
            </div>
          })}
          {showEndYear && <span className="career-end-year" style={{ right:24, top:layout.axisY + 24 }} aria-hidden="true">{layout.endYear}</span>}
        </div>
      </div>
    </>}
    {active && createPortal(<div id={id} className="career-popover" role="tooltip" onMouseEnter={() => clearTimeout(hideTimer.current)} onMouseLeave={leave} style={{ left:active.x, ...(active.above ? { bottom:active.y } : { top:active.y }) }}>
      <strong>{active.company || active.title}</strong>{active.company && <b>{active.title}</b>}
      <span className="career-detail-dates">{active.period}</span>
      {active.employment && <span className="career-detail-type">{active.employment}</span>}
      {active.verification && <p className="career-detail-verification">{active.verification}</p>}
      {active.note && <p>{active.note}</p>}{active.description && <p>{active.description}</p>}
    </div>, document.body)}
  </div>
}
