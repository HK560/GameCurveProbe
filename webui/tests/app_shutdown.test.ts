import { describe, expect, it, vi } from 'vitest'

import { initiateApplicationShutdown } from '../src/services/appShutdown'

describe('initiateApplicationShutdown', () => {
  it('does not wait for the server shutdown response before closing the page', () => {
    vi.useFakeTimers()
    const requestShutdown = vi.fn(() => new Promise<void>(() => {}))
    const closeConnections = vi.fn()
    const closeWindow = vi.fn()

    initiateApplicationShutdown(requestShutdown, closeConnections, closeWindow)

    expect(requestShutdown).toHaveBeenCalledOnce()
    expect(closeConnections).toHaveBeenCalledOnce()
    vi.advanceTimersByTime(150)
    expect(closeWindow).toHaveBeenCalledOnce()
    vi.useRealTimers()
  })
})
