import '@testing-library/jest-dom/vitest'
import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, expect, it, vi } from 'vitest'
import PreferredLocations from './PreferredLocations'

afterEach(cleanup)
it('preserves custom locations, searches, adds without case duplicates and removes', () => {
  const changed = vi.fn()
  const { container } = render(<PreferredLocations initial={['Custom Valley']} changed={changed} />)
  const input = screen.getByRole('combobox')
  fireEvent.focus(input)
  fireEvent.change(input, { target: { value: 'mum' } })
  fireEvent.keyDown(input, { key: 'Enter' })
  fireEvent.change(input, { target: { value: 'MUMBAI' } })
  fireEvent.keyDown(input, { key: 'Enter' })
  fireEvent.change(input, { target: { value: 'Remote Europe' } })
  expect(input).toBeInvalid()
  fireEvent.keyDown(input, { key: 'Enter' })
  expect(input).toBeValid()
  expect([...container.querySelectorAll<HTMLInputElement>('input[type=hidden]')].map(input => input.value)).toEqual(['Custom Valley', 'Mumbai', 'Remote Europe'])
  fireEvent.click(screen.getByRole('button', { name: 'Remove Mumbai' }))
  expect(screen.queryByRole('button', { name: 'Remove Mumbai' })).toBeNull()
  expect(changed).toHaveBeenCalledTimes(3)
})
it('supports arrow selection and Escape without submitting the parent form', () => {
  render(<PreferredLocations initial={[]} changed={() => {}} />)
  const input = screen.getByRole('combobox')
  fireEvent.focus(input)
  fireEvent.keyDown(input, { key: 'ArrowDown' })
  expect(screen.getByRole('option', { name: 'Mumbai' })).toHaveAttribute('aria-selected', 'true')
  fireEvent.keyDown(input, { key: 'Enter' })
  expect(screen.getByRole('button', { name: 'Remove Mumbai' })).toBeVisible()
  expect(input).toHaveAttribute('aria-expanded', 'false')
  expect(screen.queryByRole('listbox')).not.toBeInTheDocument()
  fireEvent.keyDown(input, { key: 'Escape' })
  expect(input).toHaveAttribute('aria-expanded', 'false')
})
