import type {
  CaptureInfo,
  LogEntry,
  NoiseResult,
  ProbeConfig,
  ProbeSnapshot,
  RoiQuality,
  RoiRect,
  SessionResult,
  WindowInfo,
} from '../types/api'

export const tutorialMeasurementFrames = [
  { phase: 'stage_start', currentPoint: 0, totalPoints: 17 },
  { phase: 'point_settle', currentPoint: 4, totalPoints: 17 },
  { phase: 'point_sampling', currentPoint: 8, totalPoints: 17 },
  { phase: 'point_retry', currentPoint: 8, totalPoints: 17 },
  { phase: 'point_done', currentPoint: 13, totalPoints: 17 },
  { phase: 'stage_completed', currentPoint: 17, totalPoints: 17 },
] as const

export interface TutorialDemo {
  previewUrl: string
  windows: WindowInfo[]
  capture: CaptureInfo
  roi: RoiRect
  roiQualityPoor: RoiQuality
  roiQualityExcellent: RoiQuality
  noise: NoiseResult
  config: ProbeConfig
  probe: ProbeSnapshot
  logs: LogEntry[]
  result: SessionResult
}

export function createTutorialDemo(): TutorialDemo {
  const previewSvg = `<svg xmlns="http://www.w3.org/2000/svg" width="960" height="540" viewBox="0 0 960 540"><defs><linearGradient id="sky" x2="0" y2="1"><stop stop-color="#1e3a5f"/><stop offset="1" stop-color="#718a9e"/></linearGradient><pattern id="grid" width="32" height="32" patternUnits="userSpaceOnUse"><path d="M0 32L32 0M-8 8L8-8M24 40L40 24" stroke="#d6c5a2" stroke-width="4"/></pattern></defs><rect width="960" height="540" fill="url(#sky)"/><path d="M0 330L180 205 330 318 520 150 710 305 850 210 960 300V540H0Z" fill="#293f43"/><rect y="360" width="960" height="180" fill="#736a50"/><rect x="210" y="250" width="420" height="235" fill="url(#grid)" opacity=".9"/><circle cx="760" cy="130" r="42" fill="#f3d89a" opacity=".85"/><text x="28" y="48" fill="white" opacity=".8" font-family="sans-serif" font-size="18">TUTORIAL DEMO · TEXTURED SCENE</text></svg>`
  const points = Array.from({ length: 17 }, (_, index) => {
    const input = index / 16
    const normalized = input <= 0.05 ? 0 : Math.min(1, Math.pow((input - 0.05) / 0.9, 1.35))
    return {
      input,
      velocity_px_s: Math.round(normalized * 7420 * 10) / 10,
      normalized_speed: Math.round(normalized * 10000) / 10000,
      stability: index === 8 ? 0.86 : 0.97,
      valid: true,
      attempts: index === 8 ? 2 : 1,
      coverage: index === 8 ? 0.91 : 0.99,
      velocity_mad: index === 8 ? 18.2 : 5.4,
    }
  })

  const config: ProbeConfig = {
    capture_fps: 120,
    point_count: 17,
    repeats: 3,
    settle_ms: 300,
    sample_ms: 700,
    range_mode: 'active_range',
    inner_deadzone: 0.05,
    outer_deadzone: 0.95,
    hotkey_enabled: true,
    hotkey_start: 'F9',
    hotkey_stop: 'F10',
    dz_target: 'inner',
    dz_step: 0.005,
    sound_enabled: true,
    auto_wake: true,
    wake_input: 'left_stick',
    start_countdown_s: 3,
    bidirectional: true,
  }

  return {
    previewUrl: `data:image/svg+xml;charset=utf-8,${encodeURIComponent(previewSvg)}`,
    windows: [{ id: 4242, title: 'Aurora Arena — Tutorial Demo', pid: 1001, width: 1920, height: 1080 }],
    capture: { window_id: 4242, title: 'Aurora Arena — Tutorial Demo', backend: 'wgc', width: 1920, height: 1080, target_fps: 120, occlusion_safe: true },
    roi: { x: 420, y: 250, width: 720, height: 430 },
    roiQualityPoor: { score: 18, level: 'poor', metrics: { gradient: 0.12, corners: 8, entropy: 0.19, tracking: 0.28 }, suggestions: ['ROI_LOW_TEXTURE'] },
    roiQualityExcellent: { score: 91, level: 'excellent', metrics: { gradient: 0.88, corners: 164, entropy: 0.91, tracking: 0.96 }, suggestions: [] },
    noise: { floor_x: 1.8, floor_y: 2.1, valid_frames: 58, confidence: 0.98 },
    config,
    probe: { active: true, output: 0.05, step: 0.005, direction: 'right', expires_in: 9.8 },
    logs: [
      { id: 'tutorial-1', timestamp: '00:00:01', level: 'info', message: '17-point steady-state measurement started' },
      { id: 'tutorial-2', timestamp: '00:00:08', level: 'sampling', message: 'Sampling input 50.0%' },
      { id: 'tutorial-3', timestamp: '00:00:09', level: 'warn', message: 'Movement unstable; retrying this point automatically' },
      { id: 'tutorial-4', timestamp: '00:00:20', level: 'success', message: 'Measurement complete; report ready' },
    ],
    result: {
      points,
      noise: { floor_x: 1.8, floor_y: 2.1, valid_frames: 58, confidence: 0.98 },
      analysis: { curve_type: 'power', confidence: 0.96, metrics: { gamma: 1.35, r_squared: 0.992, nrmse: 0.021 } },
      schema_version: 2,
      measured_at: '2026-09-04T12:00:00+08:00',
      session_id: 'tutorial-demo',
      config: { ...config },
      warnings: ['A midpoint was automatically retried after transient frame jitter.'],
    },
  }
}
