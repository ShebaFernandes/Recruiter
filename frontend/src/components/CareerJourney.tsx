import { useEffect, useId, useRef, useState } from 'react'
import { createPortal } from 'react-dom'
import type { WorkExperience } from '../types'
import { sortCareerHistory } from '../careerHistory'
import { CandidateMilestoneIcon } from './CandidateMilestoneIcon'
import { candidateMilestoneDate } from './candidateMilestoneDate'
import './career-journey.css'

const month = 2629800000
const time = (value: string | null) => value ? new Date(value).getTime() : NaN
const ongoing = (item: WorkExperience) => !item.end_date && Boolean(item.start_date) && (
  item.is_current === true || (item.is_current === undefined && (!item.date_label || /present|current|now/i.test(item.date_label)))
)
const endTime = (item: WorkExperience) => ongoing(item) ? Date.now() : time(item.end_date)
const coarseDates = (item: WorkExperience) => Boolean(item.date_label && /(?:^|\()\d{4}\s*[–—-]\s*\d{2,4}(?:$|\))/.test(item.date_label))
const duration = (months: number) => months >= 12 ? `${(months / 12).toFixed(months % 12 ? 1 : 0)} yrs` : `${months} mo`
const shortCompany = (name: string) => name
  .replace(/\s+(?:private\s+limited|pvt\.?\s+ltd\.?|limited|ltd\.?|llp|incorporated|inc\.?|corporation|corp\.?)$/i, '')
  .replace(/\s+technologies$/i, '')
  .trim() || name
const companyLabel = (name: string) => shortCompany(name)
  .replace(/\s*\([^)]{1,80}\)\s*$/, '')
  .replace(/\.com$/i, '')
  .trim() || shortCompany(name)

/** Shared by recruiter cards/drawers and the candidate's own profile. No data fetching. */
export default function CareerJourney({ items, detailed = false, showCompanyLabels = true, compactMarkers = false, profilePresentation = false, minimal = false, reverse = false, presentAtEnd = false, candidateMilestones = false }: { items: WorkExperience[]; detailed?: boolean; showCompanyLabels?: boolean; compactMarkers?: boolean; profilePresentation?: boolean; minimal?: boolean; reverse?: boolean; presentAtEnd?: boolean; candidateMilestones?: boolean }) {
  const sorted = sortCareerHistory(items)
  const displayed = reverse ? [...sorted.filter(item => item.start_date)].reverse().concat(sorted.filter(item => !item.start_date)) : sorted
  const id = useId()
  const root = useRef<HTMLDivElement>(null)
  const [active, setActive] = useState<{ key: string; title: string; company?: string; period: string; detail: string; note?: string; x: number; y: number; above: boolean } | null>(null)
  const pinned = useRef<string | null>(null)
  const hideTimer = useRef<ReturnType<typeof setTimeout> | undefined>(undefined)
  const close = () => { clearTimeout(hideTimer.current); pinned.current = null; setActive(null) }
  const leave = () => { if (pinned.current !== active?.key) hideTimer.current = setTimeout(close, 180) }
  useEffect(() => {
    const dismiss = (event: Event) => {
      if (event.type === 'keydown' && (event as KeyboardEvent).key !== 'Escape') return
      if (event.type === 'pointerdown' && (root.current?.contains(event.target as Node) || (event.target as Element).closest?.('.career-popover'))) return
      if ((event.type === 'wheel' || event.type === 'touchmove') && (event.target as Element).closest?.('.career-popover')) return
      close()
    }
    document.addEventListener('keydown', dismiss)
    document.addEventListener('pointerdown', dismiss)
    window.addEventListener('resize', dismiss)
    window.addEventListener('wheel', dismiss, { passive: true })
    window.addEventListener('touchmove', dismiss, { passive: true })
    return () => { clearTimeout(hideTimer.current); document.removeEventListener('keydown', dismiss); document.removeEventListener('pointerdown', dismiss); window.removeEventListener('resize', dismiss); window.removeEventListener('wheel', dismiss); window.removeEventListener('touchmove', dismiss) }
  }, [])
  if (!sorted.length) return <p className="muted">No employment history has been confirmed yet.</p>
  const show = (element: HTMLElement, data: Omit<NonNullable<typeof active>, 'x' | 'y' | 'above'>) => {
    clearTimeout(hideTimer.current)
    if (pinned.current !== data.key) pinned.current = null
    const box = element.getBoundingClientRect()
    const width = Math.min(320, window.innerWidth - 24)
    const above = window.innerHeight - box.bottom < 270 && box.top > 270
    setActive({ ...data, x: Math.max(12, Math.min(box.left, window.innerWidth - width - 12)), y: above ? window.innerHeight - box.top + 8 : Math.max(12, Math.min(box.bottom + 8, window.innerHeight - 262)), above })
  }
  return <>
    <div ref={root} className={`career-journey shared ${detailed ? 'detailed' : 'compact'} ${compactMarkers ? 'compact-markers' : ''} ${profilePresentation ? 'profile-presentation' : ''} ${minimal ? 'minimal-milestones' : ''} ${reverse ? 'reverse-milestones' : ''} ${presentAtEnd ? 'present-at-end' : ''}`} aria-label="Career journey" role="list" tabIndex={0}>
      {reverse && sorted.some(ongoing) && <div className="career-present" role="presentation"><span>Present</span><i aria-hidden="true" /></div>}
      {displayed.map((item, displayIndex) => {
        const index = sorted.indexOf(item)
        const start = time(item.start_date), end = endTime(item)
        const earlier = sorted.slice(0, index).filter(row => Number.isFinite(time(row.start_date)))
        // Use the union of earlier employment, not just the preceding row: nested jobs
        // must not manufacture a gap while another role was still ongoing.
        const uncertain = coarseDates(item) || earlier.some(row => !Number.isFinite(endTime(row)) || coarseDates(row))
        const latestEnd = Math.max(...earlier.map(endTime).filter(Number.isFinite))
        const gap = !uncertain && Number.isFinite(latestEnd) && start - latestEnd > 60 * 86400000 ? Math.round((start - latestEnd) / month) : 0
        const overlaps = !coarseDates(item) && earlier.some(row => !coarseDates(row) && endTime(row) > start)
        const months = !coarseDates(item) && Number.isFinite(end) && end >= start ? Math.max(1, Math.round((end - start) / month)) : 0
        const period = item.date_label || `${item.start_date?.slice(0, 7) || 'Start not specified'} — ${item.end_date?.slice(0, 7) || (ongoing(item) ? 'Present' : 'End not specified')}`
        const key = `${item.id ?? index}-${item.company}-${item.start_date}`
        const firstCompanyMarker = displayed.findIndex(row => row.company.trim().toLocaleLowerCase() === item.company.trim().toLocaleLowerCase()) === displayIndex
        const displayCompanyLabel = showCompanyLabels && (!minimal || firstCompanyMarker)
        const previousRole = sorted.slice(0, index).reverse().find(row => row.company.trim().toLowerCase() === item.company.trim().toLowerCase() && row.role !== item.role)
        const note = [overlaps ? 'Overlapping employment' : '', minimal && previousRole ? `Career progression from ${previousRole.role}` : ''].filter(Boolean).join(' · ')
        const data = { key, title: item.role || 'Role not specified', company: minimal ? companyLabel(item.company) : item.company, period: `${period}${months ? ` · ${duration(months)}` : ''}`, detail: item.description || (minimal ? '' : 'No additional work details provided.'), note: note || undefined }
        return <div className="career-sequence" key={key} style={{ flexGrow: Math.max(1, months) }}>
          {gap > 0 && <div className="career-gap-period" role="listitem"><button type="button" className="career-job career-gap-marker" aria-label={`Career gap of approximately ${gap} months`} onMouseEnter={e => show(e.currentTarget, { key: `${key}-gap`, title: 'Career gap', period: `Approximately ${duration(gap)}`, detail: item.gap_reason || 'Reason not provided by the candidate.' })} onMouseLeave={leave} onFocus={e => show(e.currentTarget, { key: `${key}-gap`, title: 'Career gap', period: `Approximately ${duration(gap)}`, detail: item.gap_reason || 'Reason not provided by the candidate.' })} onBlur={close} onClick={e => { pinned.current = `${key}-gap`; show(e.currentTarget, { key: `${key}-gap`, title: 'Career gap', period: `Approximately ${duration(gap)}`, detail: item.gap_reason || 'Reason not provided by the candidate.' }) }}><b>{duration(gap)} gap</b><span className="career-period-line" /><small>{new Date(latestEnd).getFullYear()}<i>{item.start_date?.slice(0, 4)}</i></small></button></div>}
          <div className="career-period" role="listitem">
            <button type="button" className={`career-job ${active?.key === key ? 'is-active' : ''}`} aria-label={`${data.title} at ${item.company}, ${data.period}${overlaps ? ', overlapping employment' : ''}`} aria-expanded={active?.key === key} aria-describedby={active?.key === key ? id : undefined}
              onMouseEnter={e => { if (e.buttons === 0) show(e.currentTarget, data) }} onMouseLeave={leave}
              onFocus={e => show(e.currentTarget, data)} onBlur={close}
              onClick={e => { if (pinned.current === key) close(); else { pinned.current = key; show(e.currentTarget, data) } }}>
              {displayCompanyLabel && <b>{minimal ? companyLabel(item.company) : item.company}</b>}<span className="career-period-line"><span className="career-marker-icon" aria-hidden="true"><CandidateMilestoneIcon /></span>{!compactMarkers && <><i /><i /></>}</span>
              <small><span>{candidateMilestones ? candidateMilestoneDate(item) : (reverse || minimal) && item.start_date && displayed[displayIndex - 1]?.start_date?.slice(0, 4) === item.start_date.slice(0, 4) ? '' : item.start_date?.slice(0, 4) || '?'}</span>{!compactMarkers && <i>{item.end_date?.slice(0, 4) || (ongoing(item) ? 'Now' : '?')}</i>}</small>
              {detailed && <em>{item.role}</em>}
              {profilePresentation && <span className="career-role-summary"><span className="career-initial" aria-hidden="true">{item.company.trim().charAt(0).toLocaleUpperCase() || '·'}</span><strong>{item.company || 'Employer not specified'}</strong><span>{item.role || 'Role not specified'}</span><span className="career-role-dates">{period}</span></span>}
            </button>
          </div>
        </div>
      })}
      {presentAtEnd && sorted.some(ongoing) && <div className="career-present career-present-end" role="presentation"><span>Present</span><i aria-hidden="true" /></div>}
    </div>
    {active && createPortal(<div id={id} className={`career-popover ${minimal ? 'candidate-career-popover' : ''}`} role="tooltip" onMouseEnter={() => clearTimeout(hideTimer.current)} onMouseLeave={leave} style={{ left: active.x, ...(active.above ? { bottom: active.y } : { top: active.y }) }}>{minimal ? <><strong>{active.company || active.title}</strong>{active.company && <span>{active.title}</span>}<small>{active.period}</small>{candidateMilestones && <>{active.note && <p>{active.note}</p>}{active.detail && <p>{active.detail}</p>}</>}</> : <><strong>{active.company || active.title}</strong>{active.company && <b>{active.title}</b>}<span>{active.period}</span>{active.note && <span>{active.note}</span>}{active.detail && <p>{active.detail}</p>}</>}</div>, document.body)}
  </>
}
