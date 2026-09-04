import fs from 'node:fs'
import path from 'node:path'
import { describe, expect, it } from 'vitest'
import { tutorialTargetNames } from '../src/services/tutorialSteps'

describe('tutorial anchors', () => {
  it('renders every catalog target in a Vue template', () => {
    const root = path.resolve(__dirname, '../src')
    const source = [
      'App.vue',
      'components/CaptureStep.vue',
      'components/DeadzoneStep.vue',
      'components/DeadzoneRangeSlider.vue',
      'components/MeasurementStep.vue',
      'components/AnalysisStep.vue',
    ].map(file => fs.readFileSync(path.join(root, file), 'utf8')).join('\n')
    for (const target of tutorialTargetNames) {
      expect(source, `missing data-tour=${target}`).toContain(`data-tour="${target}"`)
    }
  })

  it('leaves Driver.js popover and overlay stacking order intact', () => {
    const css = fs.readFileSync(path.resolve(__dirname, '../src/assets/main.css'), 'utf8')
    expect(css).not.toMatch(/\.driver-overlay\s*,\s*\.driver-popover\s*\{[^}]*z-index/s)
  })
})
