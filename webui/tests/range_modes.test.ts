import { describe, expect, it } from 'vitest'

import { RANGE_MODES } from '../src/types/api'


describe('measurement range modes', () => {
  it('matches the backend contract', () => {
    expect(RANGE_MODES).toEqual(['active_range', 'full'])
  })
})
