import '@testing-library/jest-dom/vitest'
import { cleanup, fireEvent, render, screen, within } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { api } from '../api'
import GrowthStages from './GrowthStages'

afterEach(() => { cleanup(); vi.restoreAllMocks() })

describe('GrowthStages', () => {
  it('opens the founding form beside the selected card and restores both cards on close', () => {
    render(<GrowthStages />)
    fireEvent.click(screen.getByRole('button', { name: /build your founding team/i }))
    const form = screen.getByRole('form', { name: 'Founding team enquiry' })
    expect(within(form).getByLabelText('Company')).toBeRequired()
    expect(within(form).getByLabelText('Your role')).toBeRequired()
    expect(screen.getByRole('heading', { name: /your first few people/i })).toBeVisible()
    expect(screen.queryByRole('heading', { name: /the right leader changes/i })).not.toBeInTheDocument()
    fireEvent.click(within(form).getByRole('button', { name: 'Founding Engineer' }))
    expect(within(form).getByRole('button', { name: 'Founding Engineer' })).toHaveAttribute('aria-pressed', 'true')
    fireEvent.click(screen.getByRole('button', { name: 'Close growth enquiry' }))
    expect(screen.queryByRole('form')).not.toBeInTheDocument()
    expect(screen.getByRole('heading', { name: /the right leader changes/i })).toBeVisible()
  })

  it('submits the founding team details and uploaded notes', async () => {
    const submit = vi.spyOn(api, 'submitHiringEnquiry').mockResolvedValue({ id: 2, detail: 'Received' })
    render(<GrowthStages />)
    fireEvent.click(screen.getByRole('button', { name: /build your founding team/i }))
    const form = screen.getByRole('form', { name: 'Founding team enquiry' })
    fireEvent.change(within(form).getByLabelText('Company'), { target: { value: 'Example Co' } })
    fireEvent.change(within(form).getByLabelText('Your name'), { target: { value: 'Alex Example' } })
    fireEvent.change(within(form).getByLabelText('Work email'), { target: { value: 'alex@example.com' } })
    fireEvent.click(within(form).getByRole('button', { name: 'Founder' }))
    fireEvent.change(within(form).getByLabelText('What are you building?'), { target: { value: 'A useful product' } })
    fireEvent.click(within(form).getByRole('button', { name: 'Founding Engineer' }))
    fireEvent.click(within(form).getByRole('button', { name: 'Bengaluru' }))
    fireEvent.change(within(form).getByLabelText('Upload JD or notes'), {
      target: { files: [new File(['Early team notes'], 'notes.txt', { type: 'text/plain' })] },
    })
    fireEvent.click(within(form).getByRole('checkbox', { name: /Your details are private/ }))
    fireEvent.submit(form)
    expect(await screen.findByRole('status')).toHaveTextContent('Your request has been received.')
    const body = submit.mock.calls[0][0]
    expect(body.get('kind')).toBe('founding')
    expect(body.get('product')).toBe('A useful product')
    expect(body.getAll('categories')).toEqual(['Founding Engineer'])
    expect(body.has('people_count')).toBe(false)
    expect((body.get('attachment') as File).name).toBe('notes.txt')
  })

  it('validates and submits the leadership search with confidentiality choice', async () => {
    const submit = vi.spyOn(api, 'submitHiringEnquiry').mockResolvedValue({ id: 3, detail: 'Received' })
    render(<GrowthStages />)
    fireEvent.click(screen.getByRole('button', { name: 'Find Leadership' }))
    const form = screen.getByRole('form', { name: 'Leadership enquiry' })
    expect(within(form).getByLabelText(/Keep this search confidential/)).toBeChecked()
    fireEvent.submit(form)
    expect(screen.getByRole('status')).toHaveTextContent('Please select at least one hiring category.')
    fireEvent.change(within(form).getByLabelText('Company'), { target: { value: 'Example Co' } })
    fireEvent.change(within(form).getByLabelText('Your name'), { target: { value: 'Alex Example' } })
    fireEvent.change(within(form).getByLabelText('Work email'), { target: { value: 'alex@example.com' } })
    fireEvent.click(within(form).getByRole('button', { name: 'Engineering Leader' }))
    fireEvent.change(within(form).getByLabelText('What needs to be fundamentally different in 12 months?'), { target: { value: 'Raise the bar' } })
    fireEvent.click(within(form).getByLabelText('Keep this search confidential'))
    fireEvent.click(within(form).getByRole('checkbox', { name: /Your details are private/ }))
    fireEvent.submit(form)
    expect(await screen.findByRole('status')).toHaveTextContent('Your request has been received.')
    const body = submit.mock.calls[0][0]
    expect(body.get('kind')).toBe('leadership')
    expect(body.getAll('categories')).toEqual(['Engineering Leader'])
    expect(body.get('role_title')).toBe('Engineering Leader')
    expect(body.get('confidential')).toBe('false')
    expect(body.get('outcome')).toBe('Raise the bar')
    expect(screen.queryByRole('heading', { name: /your first few people/i })).not.toBeInTheDocument()
  })
})
