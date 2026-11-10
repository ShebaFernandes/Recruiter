import { expect, it } from 'vitest'
import { approvedPublicOpportunityIds } from './publicationContract'
const manifest = (opportunities: Record<string, unknown> = {}) => ({ schemaVersion: 1, reviewStatus: 'reviewed', opportunities })

it('allows only explicitly approved and published synthetic jobs', () => {
  expect(approvedPublicOpportunityIds(manifest({ public: { approved: true, published: true }, draft: { approved: true, published: false } }), ['public', 'draft', 'unmarked'])).toEqual(['public'])
})
it.each([null, [], {}, { ...manifest(), opportunities: [] }, { ...manifest(), privateNotes: 'synthetic' }])('rejects invalid contract shapes', value => {
  expect(() => approvedPublicOpportunityIds(value, [])).toThrow()
})
it.each([{ unknown: { approved: true, published: true } }, { public: { approved: false, published: true } }, { public: { approved: 'true', published: true } }, { public: { approved: true, published: true, recruiter_notes: 'synthetic' } }])('rejects unknown jobs, unapproved publishing and extra fields', entries => {
  expect(() => approvedPublicOpportunityIds(manifest(entries), ['public'])).toThrow()
})
it('blocks activation while owner review is pending', () => {
  expect(() => approvedPublicOpportunityIds({ ...manifest(), reviewStatus: 'awaiting-owner-confirmation' }, [], true)).toThrow(/Owner-confirmed/)
})
it('does not mutate publication evidence or infer approval for unmarked jobs', () => {
  const input = manifest()
  expect(approvedPublicOpportunityIds(input, ['unmarked'])).toEqual([])
  expect(input).toEqual(manifest())
})
