// @vitest-environment node
import { describe, expect, it } from 'vitest'
import { readFileSync } from 'node:fs'

const tokens = readFileSync('src/design-tokens.css', 'utf8')
const theme = readFileSync('src/components/candidate-theme.css', 'utf8')

const value = (name: string) => tokens.match(new RegExp(`--enter-${name}:\\s*([^;]+);`))?.[1]

describe('shared ENTER identity', () => {
  it('keeps one palette for candidate, recruiter and portalled surfaces', () => {
    expect(value('text')).toBe('#303842')
    expect(value('primary')).toBe('#303842')
    expect(value('selected')).toBe('#DDF2F0')
    expect(value('selected-text')).toBe('#07565B')
    expect(value('highlight')).toBe('#0B7378')
    expect(theme).not.toMatch(/#[\da-f]{3,8}\b/i)
    expect(theme).not.toMatch(/--enter-(text|primary|border|highlight):/)
  })

  it('retains distinct semantic feedback instead of treating status as branding', () => {
    const colors = ['success', 'warning', 'error'].map(value)
    expect(new Set(colors).size).toBe(3)
    expect(value('success')).toBe(value('highlight'))
    for (const role of ['success', 'warning', 'error']) {
      expect(value(`${role}-soft`)).toMatch(/^#[\dA-F]{6}$/)
      expect(value(`${role}-soft`)).not.toBe(value(role))
    }
  })
})
