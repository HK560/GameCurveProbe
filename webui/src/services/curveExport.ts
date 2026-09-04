import type { FitCandidate } from './curveFitting'

export interface ControllerMetaPoint {
  x: number
  y: number
}

export interface ControllerMetaBezier {
  p1: ControllerMetaPoint
  p2: ControllerMetaPoint
}

export interface ControllerMetaCurveModel {
  id: string
  name: string
  kind: 'bezier' | 'polyline'
  color: string
  visible: boolean
  createdAt: string
  updatedAt: string
  sourceMeta: {
    kind: 'manual' | 'conversion' | 'compensation' | 'composition' | 'library' | 'remote-library' | 'file-import'
    description?: string
  }
  innerDeadzone: number
  outerDeadzone: number
  deadzoneAdjustMode: 'compress' | 'edge-only'
  bezier?: ControllerMetaBezier
  points?: ControllerMetaPoint[]
  basePoints?: ControllerMetaPoint[]
}

export interface ControllerMetaTransferItem {
  curve: ControllerMetaCurveModel
  savedAt?: string
  note?: string
}

export interface ControllerMetaTransferBundle {
  identifier: 'ControllerMeta'
  formatVersion: string
  exportKind: 'curve_transfer'
  exportTime: string
  itemCount: number
  items: ControllerMetaTransferItem[]
}

export interface ExportMeasurementPoint {
  input: number
  normalized_speed: number | null
  velocity_px_s?: number | null
  valid?: boolean
  in_analysis_range?: boolean
}

const DSE_CSV_HEADER = 'point_index(1-based),forward_x,forward_y,inv_x,inv_y,note'
const DSE_CSV_NOTE = 'inv_x=(forward_y/Ymax)*Xmax ; inv_y=(forward_x/Xmax)*Ymax'

function generateCurveId(): string {
  if (typeof crypto !== 'undefined' && crypto.randomUUID) {
    return `curve_probe_${crypto.randomUUID()}`
  }
  return `curve_probe_${Date.now().toString(36)}_${Math.random().toString(36).slice(2, 8)}`
}

function formatNumber(value: number): string {
  if (Number.isInteger(value)) return String(value)
  const rounded = Math.round(value * 1000) / 1000
  return Number.isInteger(rounded) ? String(rounded) : rounded.toString()
}

/**
 * Builds polyline points from actual measured data points without fixed 101-point interpolation.
 * If normalizeToFullScale is true: maps points in active deadzone range to 0%~100%.
 * If normalizeToFullScale is false: exports raw measured physical stick input points.
 */
export function buildMeasuredPolylinePoints(
  measuredPoints: ExportMeasurementPoint[] | null | undefined,
  candidate: FitCandidate | null,
  innerDz: number = 0.0,
  outerDz: number = 1.0,
  normalizeToFullScale = true
): ControllerMetaPoint[] {
  if (measuredPoints && measuredPoints.length >= 2) {
    const validPoints = measuredPoints.filter((p) => p.valid)
    const sourcePoints = validPoints.length >= 2 ? validPoints : measuredPoints

    // Velocity span fallback
    const vMin = Math.min(...sourcePoints.map((p) => p.velocity_px_s ?? 0))
    const vMax = Math.max(...sourcePoints.map((p) => p.velocity_px_s ?? 1))
    const vRange = vMax - vMin

    const getNormSpeed = (p: ExportMeasurementPoint): number => {
      if (typeof p.normalized_speed === 'number') {
        return Math.max(0, Math.min(1, p.normalized_speed))
      }
      if (typeof p.velocity_px_s === 'number' && vRange > 1e-6) {
        return Math.max(0, Math.min(1, (p.velocity_px_s - vMin) / vRange))
      }
      return 0
    }

    if (normalizeToFullScale) {
      const dzSpan = Math.max(0.001, outerDz - innerDz)
      const interiorPoints = sourcePoints.filter(
        (p) => p.input > innerDz + 1e-4 && p.input < outerDz - 1e-4
      )

      const mappedInterior: ControllerMetaPoint[] = interiorPoints.map((p) => {
        const u = Math.max(0, Math.min(1, (p.input - innerDz) / dzSpan))
        const w = getNormSpeed(p)
        return {
          x: Math.round(u * 10000) / 100,
          y: Math.round(w * 10000) / 100,
        }
      })

      return [
        { x: 0, y: 0 },
        ...mappedInterior,
        { x: 100, y: 100 },
      ]
    } else {
      // Raw physical stick input points:
      // First point is inner deadzone start (innerDz, 0), e.g. (5.0, 0)
      // Last point is outer deadzone end (outerDz, 100), e.g. (90.0, 100)
      // Interior measured points strictly between (innerDz, outerDz)
      const interiorPoints = sourcePoints.filter(
        (p) => p.input > innerDz + 1e-4 && p.input < outerDz - 1e-4
      )

      const mappedInterior: ControllerMetaPoint[] = interiorPoints.map((p) => ({
        x: Math.round(Math.max(0, Math.min(1, p.input)) * 10000) / 100,
        y: Math.round(getNormSpeed(p) * 10000) / 100,
      }))

      const innerX = Math.round(Math.max(0, Math.min(1, innerDz)) * 10000) / 100
      const outerX = Math.round(Math.max(0, Math.min(1, outerDz)) * 10000) / 100

      return [
        { x: innerX, y: 0 },
        ...mappedInterior,
        { x: outerX, y: 100 },
      ]
    }
  }

  // Fallback if no measured points: use candidate's normalizedPoints or standard linear points
  if (candidate?.normalizedPoints && candidate.normalizedPoints.length >= 2) {
    return candidate.normalizedPoints.map((pt) => ({ x: pt.x, y: pt.y }))
  }

  return [
    { x: 0, y: 0 },
    { x: 100, y: 100 },
  ]
}

/**
 * Build a ControllerMeta CurveModel from a fitted candidate and deadzone settings.
 */
export function buildControllerMetaCurveModel(
  candidate: FitCandidate | null,
  measuredPoints: ExportMeasurementPoint[] | null | undefined,
  innerDz: number = 0.0,
  outerDz: number = 1.0,
  curveName = 'GameCurveProbe Curve',
  normalizeToFullScale = true
): ControllerMetaCurveModel {
  const now = new Date().toISOString()
  const innerDeadzone = normalizeToFullScale ? 0 : Math.round(Math.max(0, Math.min(100, innerDz * 100)) * 100) / 100
  const outerDeadzone = normalizeToFullScale ? 0 : Math.round(Math.max(0, Math.min(100, (1.0 - outerDz) * 100)) * 100) / 100

  const base: ControllerMetaCurveModel = {
    id: generateCurveId(),
    name: curveName,
    kind: candidate?.type === 'bezier' && candidate.bezierControlPoints ? 'bezier' : 'polyline',
    color: '#4f8cff',
    visible: true,
    createdAt: now,
    updatedAt: now,
    sourceMeta: {
      kind: 'manual',
      description: 'Exported from GameCurveProbe',
    },
    innerDeadzone,
    outerDeadzone,
    deadzoneAdjustMode: 'compress',
  }

  if (base.kind === 'bezier' && candidate?.bezierControlPoints) {
    base.bezier = {
      p1: { x: candidate.bezierControlPoints.p1.x, y: candidate.bezierControlPoints.p1.y },
      p2: { x: candidate.bezierControlPoints.p2.x, y: candidate.bezierControlPoints.p2.y },
    }
  } else {
    const points = buildMeasuredPolylinePoints(measuredPoints, candidate, innerDz, outerDz, normalizeToFullScale)
    base.points = points.map((p) => ({ ...p }))
    base.basePoints = points.map((p) => ({ ...p }))
  }

  return base
}

/**
 * Build ControllerMeta curve transfer JSON string.
 */
export function buildControllerMetaJson(
  candidate: FitCandidate | null,
  measuredPoints: ExportMeasurementPoint[] | null | undefined,
  innerDz: number = 0.0,
  outerDz: number = 1.0,
  curveName = 'GameCurveProbe Curve',
  normalizeToFullScale = true
): string {
  const now = new Date().toISOString()
  const curve = buildControllerMetaCurveModel(candidate, measuredPoints, innerDz, outerDz, curveName, normalizeToFullScale)

  const bundle: ControllerMetaTransferBundle = {
    identifier: 'ControllerMeta',
    formatVersion: '1.0.0',
    exportKind: 'curve_transfer',
    exportTime: now,
    itemCount: 1,
    items: [
      {
        curve,
        savedAt: now,
        note: `GameCurveProbe Analysis (${candidate?.name || 'Curve'})${normalizeToFullScale ? ' [Normalized]' : ' [Raw Deadzone]'}`,
      },
    ],
  }

  return `${JSON.stringify(bundle, null, 2)}\n`
}

/**
 * Build ControllerMeta-compatible DSE CSV content.
 */
export function buildDseCsv(
  candidate: FitCandidate | null,
  measuredPoints: ExportMeasurementPoint[] | null | undefined,
  innerDz: number = 0.0,
  outerDz: number = 1.0,
  normalizeToFullScale = true
): string {
  const points = buildMeasuredPolylinePoints(measuredPoints, candidate, innerDz, outerDz, normalizeToFullScale)

  const rows = points.map((point, index) => {
    const pointIndex = index + 1
    const forwardX = formatNumber(point.x)
    const forwardY = formatNumber(point.y)
    const invX = forwardY
    const invY = forwardX
    return `${pointIndex},${forwardX},${forwardY},${invX},${invY},${DSE_CSV_NOTE}`
  })

  return `${[DSE_CSV_HEADER, ...rows].join('\n')}\n`
}
