import { describe, expect, it } from 'vitest'
import { likelyDirections, professionalTitle } from './candidateIdentity'

const row = { company: 'Example', role: 'Head of AI Engineering', start_date: '2020-01-01', end_date: null, description: '', gap_reason: '' }
describe('evidence-based candidate identity', () => {
  it('never uses an achievement as title or likely direction', () => {
    const profile = { headline: 'Built an evaluation service and led its engineering team.', work_experiences: [row] }
    expect(professionalTitle(profile)).toBe('Head of AI Engineering')
    expect(likelyDirections(profile)).toEqual(['AI Engineering Leadership'])
    expect(likelyDirections({ ...profile, career_preferences: { likely_directions: [profile.headline] } })).toEqual([])
  })
  it('preserves corrections and deliberately empty suggestions', () => {
    const profile = { headline: 'Platform Architect', work_experiences: [row], career_preferences: { likely_directions: [] } }
    expect(professionalTitle(profile)).toBe('Platform Architect')
    expect(likelyDirections(profile)).toEqual([])
  })
  it('does not invent identity or direction with missing history', () => {
    const profile = { headline: '', work_experiences: [] }
    expect(professionalTitle(profile)).toBe('')
    expect(likelyDirections(profile)).toEqual([])
  })
})
