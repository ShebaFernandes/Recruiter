import '@testing-library/jest-dom/vitest'
import { createRef } from 'react'
import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, expect, it, vi } from 'vitest'
import SettingsAutosave from './SettingsAutosave'
import type { SettingsAutosaveHandle } from './SettingsAutosave'

afterEach(() => { cleanup(); vi.unstubAllGlobals() })
it('cancels a scheduled close when a newer edit is still saving', async () => {
  vi.stubGlobal('matchMedia', () => ({ matches: false }))
  let release!: (ok: boolean) => void
  const save = vi.fn().mockResolvedValueOnce(true).mockImplementationOnce(() => new Promise<boolean>(resolve => { release = resolve }))
  const close = vi.fn()
  render(<SettingsAutosave ref={createRef()} formRef={createRef()} dirty={{ current: false }} flight={{ current: false }} save={save} close={close} closeOnSave field="notice"><label>Notice<select name="notice" defaultValue="30"><option>30</option><option>45</option><option>60</option></select></label></SettingsAutosave>)
  fireEvent.change(screen.getByLabelText('Notice'), { target: { value: '45' } })
  await waitFor(() => expect(screen.getByRole('status')).toHaveTextContent('Saved'))
  expect(close).not.toHaveBeenCalled()
  fireEvent.change(screen.getByLabelText('Notice'), { target: { value: '60' } })
  await waitFor(() => expect(save).toHaveBeenCalledTimes(2))
  await act(async () => { await new Promise(resolve => setTimeout(resolve, 300)) })
  expect(close).not.toHaveBeenCalled()
  expect(screen.getByRole('status')).toHaveTextContent('Saving…')
  await act(async () => release(true))
  await waitFor(() => expect(close).toHaveBeenCalledTimes(1))
  expect(save.mock.calls[1][0].get('notice')).toBe('60')
})
it('closes a single-choice editor only after successful save, including retry', async () => {
  const save = vi.fn().mockResolvedValueOnce(false).mockResolvedValue(true)
  const close = vi.fn()
  render(<SettingsAutosave ref={createRef()} formRef={createRef()} dirty={{ current: false }} flight={{ current: false }} save={save} close={close} closeOnSave field="notice"><label>Notice<select name="notice" defaultValue="30"><option>30</option><option>45</option></select></label></SettingsAutosave>)
  fireEvent.change(screen.getByLabelText('Notice'), { target: { value: '45' } })
  await screen.findByRole('alert')
  expect(close).not.toHaveBeenCalled()
  expect(screen.getByLabelText('Notice')).toHaveValue('45')
  fireEvent.click(screen.getByRole('button', { name: 'Retry' }))
  await waitFor(() => expect(close).toHaveBeenCalledTimes(1))
})
it('keeps grouped edits open during autosave, then closes on leaving the section', async () => {
  const save = vi.fn().mockResolvedValue(true)
  const { input, close } = setup(save)
  fireEvent.change(input, { target: { value: 'complete' } })
  await waitFor(() => expect(screen.getByRole('status')).toHaveTextContent('Saved'))
  expect(close).not.toHaveBeenCalled()
  fireEvent.pointerDown(document.body)
  await waitFor(() => expect(close).toHaveBeenCalled())
})
function setup(save: (data: FormData) => Promise<boolean>, type = 'text') {
  const ref = createRef<SettingsAutosaveHandle>()
  const dirty = { current: false }
  const close = vi.fn()
  render(<SettingsAutosave ref={ref} formRef={createRef()} dirty={dirty} flight={{ current: false }} save={save} close={close} field="test"><label>Value<input name="value" type={type} defaultValue="" /></label></SettingsAutosave>)
  return { input: screen.getByLabelText('Value'), ref, dirty, close }
}
it('debounces text, serializes saves and retains the latest edit during a slow response', async () => {
  let release!: (ok: boolean) => void
  const save = vi.fn().mockImplementationOnce(() => new Promise<boolean>(resolve => { release = resolve })).mockResolvedValue(true)
  const { input, dirty } = setup(save)
  fireEvent.change(input, { target: { value: 'first' } })
  fireEvent.change(input, { target: { value: 'second' } })
  expect(save).not.toHaveBeenCalled()
  await waitFor(() => expect(save).toHaveBeenCalledTimes(1))
  expect(save.mock.calls[0][0].get('value')).toBe('second')
  fireEvent.change(input, { target: { value: 'latest' } })
  expect(input).toHaveValue('latest')
  await act(async () => release(true))
  await waitFor(() => expect(screen.getByRole('status')).toHaveTextContent('Saved'))
  expect(save).toHaveBeenCalledTimes(2)
  expect(save.mock.calls[1][0].get('value')).toBe('latest')
  expect(dirty.current).toBe(false)
})
it('preserves a failed draft and retries without closing it', async () => {
  const save = vi.fn().mockResolvedValueOnce(false).mockResolvedValue(true)
  const { input, dirty, close } = setup(save)
  fireEvent.change(input, { target: { value: 'kept draft' } })
  await screen.findByRole('alert')
  expect(input).toHaveValue('kept draft')
  expect(dirty.current).toBe(true)
  expect(close).not.toHaveBeenCalled()
  fireEvent.click(screen.getByRole('button', { name: 'Retry' }))
  await waitFor(() => expect(screen.getByRole('status')).toHaveTextContent('Saved'))
  expect(dirty.current).toBe(false)
})
it('does not send invalid URLs and does not close an invalid draft', async () => {
  const save = vi.fn().mockResolvedValue(true)
  const { input, ref, dirty, close } = setup(save, 'url')
  fireEvent.change(input, { target: { value: 'https://' } })
  await act(async () => { expect(await ref.current!.flush()).toBe(false) })
  expect(save).not.toHaveBeenCalled()
  expect(dirty.current).toBe(true)
  expect(close).not.toHaveBeenCalled()
})
