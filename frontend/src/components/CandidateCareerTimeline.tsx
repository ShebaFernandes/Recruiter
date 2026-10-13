import type { WorkExperience } from '../types'
import { sortCareerHistory } from '../careerHistory'

export default function CandidateCareerTimeline({ items }: { items: WorkExperience[] }) {
  const sorted = sortCareerHistory(items)
  if (!sorted.length) return <p className="cp-muted">No career history identified yet. Add your experience using “Not quite — edit”.</p>
  return <ol className="cp-timeline" aria-label="Career journey" tabIndex={0}>{sorted.map((item, index) => {
    const earlier = sorted.slice(0, index).filter(row => row.start_date)
    const overlaps = item.start_date && earlier.some(row => row.end_date ? row.end_date > item.start_date! : /present|current|now/i.test(row.date_label || ''))
    return <li key={item.id ?? index}>
      <div className="cp-career-line" aria-hidden="true" /><strong>{item.company}</strong><span>{item.role}</span>
      <small>{item.date_label || `${item.start_date?.slice(0, 7) || 'Start not specified'} — ${item.end_date?.slice(0, 7) || 'End not specified'}`}</small>
      {overlaps && <small className="cp-muted">Overlapping role</small>}
      {item.gap_reason && <small>{item.gap_reason}</small>}
    </li>
  })}</ol>
}
