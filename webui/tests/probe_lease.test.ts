import { afterEach, describe, expect, it, vi } from 'vitest'

import { createProbeLease } from '../src/services/probeLease'


describe('probe lease', () => {
  afterEach(() => vi.useRealTimers())

  it('renews every 500ms and stops the probe during cleanup', async () => {
    vi.useFakeTimers()
    const renew = vi.fn().mockResolvedValue(undefined)
    const stop = vi.fn().mockResolvedValue(undefined)
    const lease = createProbeLease(renew, stop)

    lease.start()
    await vi.advanceTimersByTimeAsync(1100)
    await lease.dispose()

    expect(renew).toHaveBeenCalledTimes(2)
    expect(stop).toHaveBeenCalledTimes(1)
  })
})
