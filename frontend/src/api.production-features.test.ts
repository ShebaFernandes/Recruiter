import { afterEach, expect, it, vi } from 'vitest'
import { api } from './api'

afterEach(() => vi.unstubAllGlobals())
it('sends the exact production ownership and employment contracts with session credentials', async () => {
  const fetch = vi.fn().mockImplementation(async () => new Response(JSON.stringify({})))
  vi.stubGlobal('fetch', fetch)
  await api.confirmResumeOwnership(8, 2, 'synthetic-password')
  expect(fetch).toHaveBeenLastCalledWith(expect.stringContaining('/candidate/resumes/8/confirm-ownership/'), expect.objectContaining({ method: 'POST', credentials: 'include', body: JSON.stringify({ version: 2, password: 'synthetic-password', confirmation: true }) }))
  await api.updateEmployment(7, { company: 'Synthetic Studio' })
  expect(fetch).toHaveBeenLastCalledWith(expect.stringContaining('/candidate/work-experiences/7/'), expect.objectContaining({ method: 'PATCH', credentials: 'include', body: JSON.stringify({ company: 'Synthetic Studio' }) }))
})
