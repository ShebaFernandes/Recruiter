import type { WorkExperience, YearMonth } from '../types'
import { ongoing } from './careerTimelineLayout'

const months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']

export function roleDateInput(item: WorkExperience, side: 'start' | 'end') {
  const label = (item.date_label || '').split(/\s+[–—-]\s+/, 2)[side === 'start' ? 0 : 1]?.trim() || ''
  if (/^(?:19|20)\d{2}$/.test(label)) return { month: '', year: label, yearOnly: true }
  const saved = item[`${side}_date`]
  const iso = saved?.match(/^((?:19|20)\d{2})-(0[1-9]|1[0-2])-/)
  if (iso) return { month: `${iso[1]}-${iso[2]}`, year: iso[1], yearOnly: false }
  const text = label.match(/^([A-Za-z]+)\s+((?:19|20)\d{2})$/)
  const monthIndex = text ? months.findIndex(month => text[1].toLowerCase().startsWith(month.toLowerCase())) : -1
  if (text && monthIndex >= 0) return { month: `${text[2]}-${String(monthIndex + 1).padStart(2, '0')}`, year: text[2], yearOnly: false }
  return { month: '', year: '', yearOnly: false }
}

export function roleMissingDetails(item: WorkExperience) {
  const missing: string[] = []
  if (!item.company.trim()) missing.push('employer')
  if (!item.role.trim()) missing.push('job title')
  const start = roleDateInput(item, 'start')
  const end = roleDateInput(item, 'end')
  if (!start.month && !start.yearOnly) missing.push('start date')
  if (!ongoing(item) && !end.month && !end.yearOnly) missing.push('end date')
  return missing
}

export function yearMonthValue(month: string, year: string, yearOnly: boolean): YearMonth {
  if (yearOnly) return { year: year ? Number(year) : null, month: null }
  const match = month.match(/^((?:19|20)\d{2})-(0[1-9]|1[0-2])$/)
  return match ? { year:Number(match[1]), month:Number(match[2]) } : { year:null, month:null }
}
