import { describe, expect, it } from 'vitest'
import { validWorkEmail, validateWorkEmailInput } from './workEmail'

describe('work email validation', () => {
  it.each(['gmail.com', 'googlemail.com', 'yahoo.co.in', 'outlook.com', 'icloud.com', 'proton.me'])('rejects personal provider %s', domain => {
    expect(validWorkEmail(`person@${domain.toUpperCase()}`)).toBe(false)
  })
  it('accepts company addresses and rejects malformed input', () => {
    expect(validWorkEmail('person@company.example')).toBe(true)
    expect(validWorkEmail('invalid')).toBe(false)
  })
  it('clears the browser error after correcting the address', () => {
    const input = document.createElement('input')
    input.value = 'person@gmail.com'
    validateWorkEmailInput(input)
    expect(input.validity.customError).toBe(true)
    input.value = 'person@company.example'
    validateWorkEmailInput(input)
    expect(input.validity.customError).toBe(false)
  })
})
