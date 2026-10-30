import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import ForTalent from './ForTalent'

describe('ForTalent', () => {
  it('renders the approved content once and opens the existing candidate entry flow', () => {
    const onJoin = vi.fn()
    render(<ForTalent onJoin={onJoin} />)

    expect(screen.getByRole('heading', { name: "Let's find work that feels great." })).toBeTruthy()
    expect(screen.getByText("Find opportunities with ambitious companies building what's next.")).toBeTruthy()
    expect(screen.getByText('AI & ML · ENGINEERING · PRODUCT · LEADERSHIP')).toBeTruthy()
    expect(screen.getAllByRole('listitem').map(item => item.textContent)).toEqual(['AI & ML', 'Engineering', 'Product', 'Leadership'])

    fireEvent.click(screen.getByRole('button', { name: 'Join enter’s talent network' }))
    expect(onJoin).toHaveBeenCalledOnce()
  })
})
