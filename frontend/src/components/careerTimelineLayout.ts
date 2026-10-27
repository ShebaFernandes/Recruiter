import type { WorkExperience } from '../types'

export const time = (value: string | null) => value && /^\d{4}-\d{2}-\d{2}$/.test(value) ? new Date(value).getTime() : NaN
export const ongoing = (item: WorkExperience) => !item.end_date && (
  item.is_current === true || (item.is_current === undefined && (
    /\b(?:present|current|now)\b/i.test(item.date_label || '')
  ))
)
export const coarseDates = (item: WorkExperience) => Boolean(item.date_label && (
  /^\s*\(?\d{4}\s*[–—-]\s*(?:\d{2,4}|present|current|now)\)?\s*$/i.test(item.date_label)
))
export const endTime = (item: WorkExperience, now = Date.now()) => ongoing(item) ? now : time(item.end_date)

// "Jul 2026" covers that month. Exact ISO dates retain their exact coordinate.
// Keep this presentation boundary separate from the saved date/evidence.
export function periodEndTime(item: WorkExperience, now = Date.now()) {
  const end = endTime(item, now)
  const month = item.date_label?.match(/\b(Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)\s+(\d{4})\s*$/i)
  if (!ongoing(item) && Number.isFinite(end) && month) {
    const date = new Date(end)
    const monthIndex = ['jan','feb','mar','apr','may','jun','jul','aug','sep','oct','nov','dec'].indexOf(month[1].slice(0, 3).toLowerCase())
    if (date.getUTCDate() === 1 && date.getUTCMonth() === monthIndex && date.getUTCFullYear() === Number(month[2])) return Date.UTC(date.getUTCFullYear(), monthIndex + 1, 1)
  }
  return end
}

// A role title is direct evidence. Never infer an internship from duration,
// age, employer, descriptions of other people, or candidate-wide preferences.
export function isInternship(item: WorkExperience) {
  const explicitTitle = item.role.split(/[|/;]/).some(title =>
    /\b(?:intern|internship)\s*\)?\s*(?:$|[-–—:])/i.test(title.trim()))
  if (!item.employment_type?.trim()) return explicitTitle
  if (!/^(intern|internship)$/i.test(item.employment_type.trim())) return false
  return explicitTitle || item.confidence_status === 'supported' || item.confidence_status === 'candidate_confirmed'
}
const calendarMonth = (timestamp: number) => {
  const date = new Date(timestamp)
  return date.getUTCFullYear() * 12 + date.getUTCMonth() + (date.getUTCDate() - 1) / new Date(Date.UTC(date.getUTCFullYear(), date.getUTCMonth() + 1, 0)).getUTCDate()
}

/** Real dates share one scale. Incomplete dates are preserved off the dated axis. */
export function careerTimelineLayout(items: WorkExperience[], now = Date.now(), markerOnly = false) {
  const starts = items.filter(item => !coarseDates(item)).map(item => time(item.start_date)).filter(Number.isFinite)
  const origin = starts.length ? calendarMonth(Math.min(...starts)) : 0
  const distinctStarts = [...new Set(starts.map(calendarMonth))].sort((a, b) => a - b)
  const closestStarts = Math.min(...distinctStarts.slice(1).map((start, index) => start - distinctStarts[index]))
  const singleDuration = items.length === 1 && starts.length === 1 && Number.isFinite(periodEndTime(items[0], now))
    ? calendarMonth(periodEndTime(items[0], now)) - origin : 0
  // A single known period gets a readable axis, without inventing dates.
  // Expand the entire date scale uniformly so ordinary successive roles read
  // along one horizontal row. Very close/simultaneous starts retain label lanes.
  const scale = singleDuration > 0 ? 360 / singleDuration : (markerOnly ? Math.max(8, Math.min(24, 64 / closestStarts)) : Math.max(24, Math.min(96, 264 / closestStarts)))
  const x = (timestamp: number) => (calendarMonth(timestamp) - origin) * scale
  const labelHeight = Math.max(130, ...items.map(item => 64 + Math.ceil(item.company.length / 28) * 20 + Math.ceil(item.role.length / 30) * 18))
  const datedEnd = Math.max(0, ...items.filter(item => !coarseDates(item) && Number.isFinite(time(item.start_date))).map(item => x(Math.max(time(item.start_date), Number.isFinite(periodEndTime(item, now)) ? periodEndTime(item, now) : time(item.start_date)))))
  const labelWidth = markerOnly ? 44 : 240
  const lanes: number[] = []
  const barLanes: number[] = []
  let right = datedEnd + 80
  let unknownX = starts.length ? (markerOnly ? datedEnd + 100 : Math.max(280, datedEnd + 280)) : 0
  const rows = items.map(item => {
    const start = time(item.start_date), end = periodEndTime(item, now)
    const dated = Number.isFinite(start) && !coarseDates(item)
    const left = dated ? x(start) : unknownX
    const span = dated && Number.isFinite(end) && end >= start ? x(end) - left : 0
    let lane = lanes.findIndex(edge => edge + 24 <= left)
    if (lane < 0) lane = lanes.length
    lanes[lane] = left + labelWidth
    let barLane = barLanes.findIndex(edge => edge <= left)
    if (barLane < 0) barLane = barLanes.length
    if (dated) barLanes[barLane] = left + span
    right = Math.max(right, left + Math.max(labelWidth, span))
    if (!dated) unknownX += markerOnly ? 100 : 280
    return { left, span, lane, barLane, dated }
  })
  return { rows, width: right + 24, height: 65 + lanes.length * labelHeight, labelHeight, datedEnd, x }
}
