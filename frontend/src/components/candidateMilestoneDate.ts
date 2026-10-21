import type { WorkExperience } from '../types'

/** Compact visible milestones; full saved dates remain in the detail popover. */
export function candidateMilestoneDate(item: WorkExperience) {
  if (!item.start_date) return 'Date unknown'
  return item.start_date.slice(0, 4)
}
