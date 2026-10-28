import type { WorkExperience } from '../types'
import { careerStartYear } from '../careerHistory'

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

/** Keep one date axis. Compact only markers whose touch targets would collide. */
export function fittedCareerTimeline(items: WorkExperience[], width: number, now = Date.now()) {
  const padding = 24
  const usable = Math.max(1, width - padding * 2)
  const dated = items.map(item => !coarseDates(item) ? time(item.start_date) : NaN)
  const starts = dated.filter(Number.isFinite)
  const unknownIndices = dated.flatMap((value, index) => Number.isFinite(value) ? [] : [index])
  const datedUsable = Math.max(1, usable - (starts.length && unknownIndices.length ? 56 : 0))
  const ends = items.flatMap((item, index) => {
    if (!Number.isFinite(dated[index])) return []
    const end = periodEndTime(item, now)
    return Number.isFinite(end) && end >= dated[index] ? [end] : []
  })
  const minimum = starts.length ? Math.min(...starts) : NaN
  const maximum = starts.length ? Math.max(...starts, ...ends) : NaN
  const minMonth = Number.isFinite(minimum) ? calendarMonth(minimum) : NaN
  const maxMonth = Number.isFinite(maximum) ? calendarMonth(maximum) : NaN
  const dateX = (value: number) => Number.isFinite(value) && Number.isFinite(minMonth)
    ? padding + (maxMonth > minMonth ? (calendarMonth(value) - minMonth) / (maxMonth - minMonth) : .5) * datedUsable
    : NaN
  const positions = items.map((item, index) => {
    const isDated = Number.isFinite(dated[index])
    const x = isDated ? dateX(dated[index]) : (starts.length ? width - padding : width / 2)
    const end = periodEndTime(item, now)
    const endX = isDated && Number.isFinite(end) && end >= dated[index] ? dateX(end) : NaN
    return { x, dated:isDated, span:Number.isFinite(endX) ? Math.max(0, endX - x) : 0 }
  })
  type Group = { members:number[]; x:number; dated:boolean }
  const groups:Group[] = []
  const datedIndices = dated.flatMap((value, index) => Number.isFinite(value) ? [index] : [])
  const slots = Math.max(1, Math.floor(datedUsable / 48))
  if (datedIndices.length > slots) {
    const bins = new Map<number, number[]>()
    for (const index of datedIndices) {
      const slot = Math.min(slots - 1, Math.floor((positions[index].x - padding) / datedUsable * slots))
      bins.set(slot, [...(bins.get(slot) || []), index])
    }
    for (const [slot, members] of bins) groups.push({
      members, x:padding + (slot + .5) * datedUsable / slots, dated:true,
    })
  } else {
    for (const index of datedIndices) {
      const previous = groups.at(-1)
      if (previous && positions[index].x - previous.x < 44) {
        previous.members.push(index)
        previous.x = previous.members.reduce((total, member) => total + positions[member].x, 0) / previous.members.length
      } else groups.push({ members:[index], x:positions[index].x, dated:true })
    }
  }
  if (unknownIndices.length) groups.push({
    members:unknownIndices, x:starts.length ? width - padding : width / 2, dated:false,
  })
  const axisY = 28
  const height = 102
  const yearGap = width < 500 ? 58 : 42
  const endYear = Number.isFinite(maximum) ? new Date(maximum).getUTCFullYear() : null
  let previousYearX = -Infinity
  const seenYears = new Set<string>()
  const yearLabels = items.map(() => '')
  for (const group of groups) {
    if (!group.dated) continue
    const year = careerStartYear(items[group.members[0]])
    if (endYear !== null && year !== String(endYear) && group.x > width - padding - yearGap) continue
    if (!year || seenYears.has(year) || group.x - previousYearX < yearGap) continue
    seenYears.add(year)
    previousYearX = group.x
    yearLabels[group.members[0]] = year
  }
  if (!starts.length && unknownIndices.length === 1) {
    yearLabels[unknownIndices[0]] = careerStartYear(items[unknownIndices[0]]) || ''
  }
  return { positions, groups, axisY, height, dateX, yearLabels, hasDated:starts.length > 0,
    endYear }
}
