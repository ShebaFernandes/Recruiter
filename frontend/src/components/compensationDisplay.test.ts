import { expect, it } from 'vitest'
import { compensationDisplay } from './compensationDisplay'

it('removes only redundant fractional zeros, never rounding compensation', () => {
  for (const [value, expected] of [['20.00', '20'], ['30.00', '30'], ['20.50', '20.5'], ['0.00', '0'], ['200', '200'], ['12345678901234567890.12', '12345678901234567890.12'], ['20.01', '20.01']]) {
    expect(compensationDisplay(value)).toBe(expected)
  }
  expect(compensationDisplay(null)).toBe('')
})
