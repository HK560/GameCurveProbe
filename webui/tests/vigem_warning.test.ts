import { describe, expect, it, vi } from 'vitest'
import {
  VIGEM_WARNING_DISMISSED_KEY,
  dismissVigemWarning,
  shouldShowVigemWarning,
} from '../src/services/vigemWarning'

describe('ViGEmBus warning persistence', () => {
  it('shows only after a successful health check reports the driver unavailable', () => {
    const storage = { getItem: vi.fn(() => null), setItem: vi.fn() }

    expect(shouldShowVigemWarning(true, false, storage)).toBe(true)
    expect(shouldShowVigemWarning(true, true, storage)).toBe(false)
    expect(shouldShowVigemWarning(false, false, storage)).toBe(false)
  })

  it('persists dismissal and suppresses future warnings', () => {
    const values = new Map<string, string>()
    const storage = {
      getItem: (key: string) => values.get(key) ?? null,
      setItem: (key: string, value: string) => { values.set(key, value) },
    }

    dismissVigemWarning(storage)

    expect(values.get(VIGEM_WARNING_DISMISSED_KEY)).toBe('1')
    expect(shouldShowVigemWarning(true, false, storage)).toBe(false)
  })

  it('degrades safely when storage is unavailable', () => {
    const storage = {
      getItem: vi.fn(() => { throw new Error('blocked') }),
      setItem: vi.fn(() => { throw new Error('blocked') }),
    }

    expect(shouldShowVigemWarning(true, false, storage)).toBe(true)
    expect(() => dismissVigemWarning(storage)).not.toThrow()
  })
})
