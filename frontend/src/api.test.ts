import { afterEach, describe, expect, it, vi } from 'vitest'
import { api } from './api'

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('API recovery messages', () => {
  it('replaces browser network errors with a useful connection message', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new TypeError('Failed to fetch')))
    await expect(api.me()).rejects.toMatchObject({
      code: 'connection',
      message: 'We can’t reach Enter right now. Check your connection and try again.',
    })
  })

  it('preserves backend rate-limit recovery guidance', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(
        new Response(
          JSON.stringify({
            detail: 'Too many requests. Please try again in 42 seconds.',
            code: 'rate_limited',
          }),
          { status: 429, headers: { 'Content-Type': 'application/json' } },
        ),
      ),
    )
    await expect(api.me()).rejects.toMatchObject({
      status: 429,
      code: 'rate_limited',
      message: 'Too many requests. Please try again in 42 seconds.',
    })
  })

  it('announces authentication expiry so the app can return to sign-in', async () => {
    const expired = vi.fn()
    window.addEventListener('enter-auth-expired', expired, { once: true })
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(
        new Response(JSON.stringify({ detail: 'Invalid token.' }), {
          status: 401,
          headers: { 'Content-Type': 'application/json' },
        }),
      ),
    )
    await expect(api.me()).rejects.toMatchObject({ code: 'auth_expired' })
    expect(expired).toHaveBeenCalledOnce()
  })

  it('preserves a recoverable AI-search service message', async () => {
    const response = new Response(
      JSON.stringify({
        detail: 'Enter could not understand this search right now. Please try again shortly.',
        code: 'search_understanding_unavailable',
      }),
      { status: 503, headers: { 'Content-Type': 'application/json' } },
    )
    vi.stubGlobal(
      'fetch',
      vi.fn()
        .mockResolvedValueOnce(
          new Response(JSON.stringify({ csrfToken: 'test-csrf' }), {
            status: 200,
            headers: { 'Content-Type': 'application/json' },
          }),
        )
        .mockResolvedValueOnce(response),
    )

    await expect(api.createSearch('AI Full-Stack Developer remote')).rejects.toMatchObject({
      status: 503,
      code: 'search_understanding_unavailable',
      message: 'Enter could not understand this search right now. Please try again shortly.',
    })
  })
})
