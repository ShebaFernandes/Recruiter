import '@testing-library/jest-dom/vitest'
import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, expect, it } from 'vitest'
import { LegalChecks } from './LegalReview'
import type { LegalDocuments } from '../legalReview'

afterEach(cleanup)
const documents = Object.fromEntries(['terms', 'privacy', 'age', 'submission'].map(purpose => [purpose, {
  text: purpose === 'age' ? 'I confirm that I am at least 18 years old.' : 'Published synthetic document',
  version: `enter-candidate-${purpose}-v1.0`, sha256: 'fixture', unpublished: false,
}])) as LegalDocuments

it('requires independent unchecked age and Terms controls without sharing consent', () => {
  const { container } = render(<form><LegalChecks documents={documents} /><button>Continue</button></form>)
  const checks = screen.getAllByRole('checkbox') as HTMLInputElement[]
  expect(checks).toHaveLength(2)
  expect(checks.every(check => !check.checked && check.required)).toBe(true)
  expect(container.querySelector('form')?.checkValidity()).toBe(false)
  fireEvent.click(checks[0])
  expect(checks[1]).not.toBeChecked()
  expect(container.querySelector('form')?.checkValidity()).toBe(false)
  fireEvent.click(checks[1])
  expect(container.querySelector('form')?.checkValidity()).toBe(true)
  expect(screen.getByRole('link', { name: /Terms/ })).toHaveAttribute('href', '/terms')
  expect(screen.getByRole('link', { name: /Privacy Policy/ })).toHaveAttribute('href', '/privacy')
  expect(container.querySelector('input[name=terms_version]')).toHaveValue(documents.terms.version)
})
