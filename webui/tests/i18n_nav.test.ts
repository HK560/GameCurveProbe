import { describe, expect, it } from 'vitest'
import { messages } from '../src/services/i18n'

describe('Navigation i18n keys', () => {
  const requiredKeys = [
    'back_to_capture',
    'back_to_deadzone',
    'back_to_measurement',
    'proceed_to_deadzone',
    'proceed_to_measurement',
    'proceed_to_analysis',
    'restart_test',
  ] as const

  it('contains all navigation keys in zh', () => {
    for (const key of requiredKeys) {
      expect((messages.zh as any)[key]).toBeDefined()
      expect(typeof (messages.zh as any)[key]).toBe('string')
      expect((messages.zh as any)[key].length).toBeGreaterThan(0)
    }
  })

  it('contains all navigation keys in en', () => {
    for (const key of requiredKeys) {
      expect((messages.en as any)[key]).toBeDefined()
      expect(typeof (messages.en as any)[key]).toBe('string')
      expect((messages.en as any)[key].length).toBeGreaterThan(0)
    }
  })
})
