import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { api } from '../api'
import WhenTeamsChange from './WhenTeamsChange'

vi.mock('../api', () => ({ api: { submitEmployeeTransitionEnquiry: vi.fn() } }))

afterEach(() => { cleanup(); vi.clearAllMocks() })

describe('WhenTeamsChange', () => {
  it('renders the shortened transition story on a plain surface', () => {
    render(<WhenTeamsChange />)

    expect(screen.getByRole('heading', { name: /The impact we create extends across entire organizations/i })).toBeTruthy()
    expect(screen.getByText('When roles end, responsibility doesn’t have to.')).toBeTruthy()
    expect(screen.getByText('Because every exit deserves the possibility of an entrance.')).toBeTruthy()

    expect(Array.from(document.querySelectorAll('.when-teams-change__copy p'), paragraph => paragraph.textContent)).toEqual([
      'A layoff may be a business decision. For the person receiving it, it can change everything overnight.',
      'enter helps you make that transition a little less difficult.',
      'Give impacted employees a direct path into our hiring network, where their experience is understood, their work is represented with context, and they can be considered for opportunities where they genuinely belong.',
    ])

    expect(document.querySelector('.when-teams-change__images')).toBeNull()
  })

  it('opens the compact support form and restores focus after Escape', () => {
    render(<WhenTeamsChange />)
    const trigger = screen.getByRole('button', { name: /support your people/i })
    fireEvent.click(trigger)

    const dialog = screen.getByRole('dialog', { name: 'Help your people find what’s next.' })
    expect(dialog.textContent).toContain('How should we reach your people?')
    expect(screen.getByRole('textbox', { name: 'Company' })).toBeTruthy()
    expect(screen.getByRole('radio', { name: /Upload a list/i })).toBeTruthy()
    expect(screen.getByRole('radio', { name: /Talk to us first/i })).toBeTruthy()
    expect(dialog.textContent).not.toContain('No request is sent from this preview.')
    expect(screen.getByLabelText('Choose an Excel or CSV list').getAttribute('accept')).toContain('.xlsx')

    fireEvent.keyDown(document, { key: 'Escape' })
    expect(screen.queryByRole('dialog')).toBeNull()
    expect(document.activeElement).toBe(trigger)
  })

  it('submits the talk path without a file', async () => {
    vi.mocked(api.submitEmployeeTransitionEnquiry).mockResolvedValue({ id: 1, detail: 'Received' })
    render(<WhenTeamsChange />)
    fireEvent.click(screen.getByRole('button', { name: /support your people/i }))
    fireEvent.click(screen.getByRole('radio', { name: /Talk to us first/i }))
    expect(screen.queryByLabelText('Choose an Excel or CSV list')).toBeNull()
    fireEvent.change(screen.getByLabelText('Tell us about the situation'), { target: { value: 'Help our team find new roles.' } })
    fireEvent.submit(screen.getByRole('button', { name: 'Submit' }).closest('form')!)
    await waitFor(() => expect(api.submitEmployeeTransitionEnquiry).toHaveBeenCalledOnce())
    const body = vi.mocked(api.submitEmployeeTransitionEnquiry).mock.calls[0][0]
    expect(body.get('reach_method')).toBe('talk')
    expect(body.get('situation')).toBe('Help our team find new roles.')
    expect(body.has('employee_list')).toBe(false)
    expect(await screen.findByText(/Your request has been received/)).toBeTruthy()
  })
})
