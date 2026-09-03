export const RANGE_MODES = ['active_range', 'full'] as const
export type RangeMode = (typeof RANGE_MODES)[number]

export type JobState =
  | 'queued'
  | 'running'
  | 'canceling'
  | 'completed'
  | 'canceled'
  | 'failed'

export interface ProbeConfig {
  capture_fps: number
  point_count: number
  repeats: number
  settle_ms: number
  sample_ms: number
  range_mode: RangeMode
  inner_deadzone: number
  outer_deadzone: number
  hotkey_enabled?: boolean
  hotkey_start?: string
  hotkey_stop?: string
  hotkey_dz_inc?: string
  hotkey_dz_dec?: string
  dz_target?: 'inner' | 'outer'
  dz_step?: number
  sound_enabled?: boolean
  wake_input?: string
  auto_wake?: boolean
  start_countdown_s?: number
}

export interface RoiRect {
  x: number
  y: number
  width: number
  height: number
}

export interface CaptureInfo {
  window_id: number
  backend: string
  width: number
  height: number
  target_fps: number
  title?: string
  occlusion_safe: boolean
}

export interface CaptureHealth {
  is_healthy: boolean
  fps: number
  duplicate_ratio: number
  last_error?: string | null
  frame_id: number
  frame_age_ms?: number | null
  window_exists: boolean
  window_minimized: boolean
}

export interface MeasurementPoint {
  input: number
  velocity_px_s: number | null
  normalized_speed: number | null
  stability: number
  valid: boolean
  attempts: number
}

export interface NoiseResult {
  floor_x: number
  floor_y: number
  valid_frames: number
  confidence: number
}

export interface RoiQuality {
  score: number
  level: 'poor' | 'fair' | 'good' | 'excellent'
  metrics: {
    gradient: number
    corners: number
    entropy: number
    tracking: number
  }
  suggestions: string[]
}

export interface CurveAnalysis {
  curve_type: string
  confidence: number
  metrics: Record<string, number>
}

export interface SessionResult {
  points: MeasurementPoint[]
  noise?: NoiseResult | null
  analysis?: CurveAnalysis | null
  schema_version: number
  measured_at: string
  session_id?: string
  environment?: Record<string, any>
  config?: Record<string, any>
  warnings?: string[]
}

export type LogLevel = 'info' | 'action' | 'settle' | 'sampling' | 'warn' | 'success' | 'error'

export interface LogEntry {
  id: string
  timestamp: string
  level: LogLevel
  message: string
}

export interface JobProgress {
  phase?: string
  current_point?: number
  total_points?: number
  input_value?: number
  message?: string
  point?: MeasurementPoint
  range_mode?: string
  settle_ms?: number
  sample_ms?: number
  valid_points?: number
  [key: string]: any
}

export interface JobSnapshot {
  id: string
  kind: string
  state: JobState
  progress?: JobProgress | null
  result?: any | null
  error?: string | null
  created_at?: string
  updated_at?: string
}

export interface SessionSnapshot {
  id: string
  config: ProbeConfig
  roi?: RoiRect | null
  capture?: CaptureInfo | null
  roi_quality?: RoiQuality | null
  last_job?: JobSnapshot | null
  active_job?: JobSnapshot | null
  last_result?: SessionResult | null
  noise?: NoiseResult | null
}

export interface WindowInfo {
  id: number
  title: string
  pid?: number | null
  width: number
  height: number
}

export interface ProbeSnapshot {
  active: boolean
  output: number
  step: number
  direction: string
  expires_in: number
}

export interface ApiError {
  code: string
  message: string
  details?: Record<string, any>
}
