// Staged publication contract only. No runtime catalog or permission changes.
export function approvedPublicOpportunityIds(value: unknown, knownIds: readonly string[], requireReviewed = false): string[] {
  if (!value || typeof value !== 'object' || Array.isArray(value)) throw new Error('Invalid publication manifest')
  const manifest = value as Record<string, unknown>
  if (Object.keys(manifest).some(key => !['$schema', 'schemaVersion', 'reviewStatus', 'opportunities'].includes(key)) ||
      (manifest.$schema !== undefined && typeof manifest.$schema !== 'string') || manifest.schemaVersion !== 1 ||
      !['awaiting-owner-confirmation', 'reviewed'].includes(String(manifest.reviewStatus)) ||
      !manifest.opportunities || typeof manifest.opportunities !== 'object' || Array.isArray(manifest.opportunities)) {
    throw new Error('Invalid publication manifest contract')
  }
  if (requireReviewed && manifest.reviewStatus !== 'reviewed') throw new Error('Owner-confirmed publication statuses are required before activation')
  const approved = new Set<string>()
  for (const [id, value] of Object.entries(manifest.opportunities)) {
    if (!knownIds.includes(id) || !value || typeof value !== 'object' || Array.isArray(value)) throw new Error('Invalid opportunity publication entry')
    const entry = value as Record<string, unknown>
    if (Object.keys(entry).some(key => !['approved', 'published'].includes(key)) || typeof entry.approved !== 'boolean' || typeof entry.published !== 'boolean') throw new Error('Invalid opportunity publication entry')
    if (entry.published && !entry.approved) throw new Error('An unapproved opportunity cannot be published')
    if (entry.approved && entry.published) approved.add(id)
  }
  return knownIds.filter(id => approved.has(id))
}
