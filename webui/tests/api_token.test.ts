import { beforeEach, describe, expect, it, vi } from 'vitest'

import { ApiClient } from '../src/services/api'


describe('ApiClient token bootstrap', () => {
  beforeEach(() => {
    vi.unstubAllGlobals()
  })

  it('consumes token from the fragment, clears it, and never persists it', () => {
    const replaceState = vi.fn()
    const persistentStorage = { setItem: vi.fn(), getItem: vi.fn() }
    vi.stubGlobal('window', {
      location: { hash: '#token=fragment-secret', pathname: '/', search: '' },
      history: { replaceState },
    })
    vi.stubGlobal('localStorage', persistentStorage)

    const client = new ApiClient()

    expect(client.getToken()).toBe('fragment-secret')
    expect(replaceState).toHaveBeenCalledWith({ gcpToken: 'fragment-secret' }, '', '/')
    expect(persistentStorage.setItem).not.toHaveBeenCalled()
    expect(persistentStorage.getItem).not.toHaveBeenCalled()
  })

  it('restores the in-memory session token after a page reload', () => {
    const persistentStorage = { setItem: vi.fn(), getItem: vi.fn() }
    vi.stubGlobal('window', {
      location: { hash: '', pathname: '/', search: '' },
      history: { state: { gcpToken: 'history-secret' }, replaceState: vi.fn() },
    })
    vi.stubGlobal('localStorage', persistentStorage)

    const client = new ApiClient()

    expect(client.getToken()).toBe('history-secret')
    expect(persistentStorage.setItem).not.toHaveBeenCalled()
    expect(persistentStorage.getItem).not.toHaveBeenCalled()
  })
})
