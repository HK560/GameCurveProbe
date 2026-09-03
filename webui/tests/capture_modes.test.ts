import { describe, expect, it } from 'vitest'

import { captureModeInfo } from '../src/services/captureModes'

describe('capture mode descriptions', () => {
  it('marks automatic WGC capture as occlusion-safe', () => {
    expect(captureModeInfo('auto').occlusionSafe).toBe(true)
  })

  it('warns that dxcam captures covering windows', () => {
    expect(captureModeInfo('dxcam').warning).toContain('遮挡')
  })
})
