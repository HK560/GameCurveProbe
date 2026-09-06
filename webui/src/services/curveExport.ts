/**
 * Curve export and import utilities for ControllerMeta and CSV formats.
 */

import type { FitCandidate } from './curveFitting'
import type { SessionResult, MeasurementPoint } from '../types/api'

export interface ControllerMetaCurvePoint {
  x: number
  y: number
}

export interface ControllerMetaBezierControlPoints {
  p1: ControllerMetaCurvePoint
  p2: ControllerMetaCurvePoint
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
  bezier?: ControllerMetaBezierControlPoints
  points?: ControllerMetaCurvePoint[]
  basePoints?: ControllerMetaCurvePoint[]
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
  velocity_px_s: number | null
  normalized_speed?: number | null
  valid?: boolean
  in_analysis_range?: boolean
}

export type CurveExportContentMode = 'normalized_and_fitted' | 'raw_with_deadzone'

const DSE_CSV_HEADER = 'point_index(1-based),forward_x,forward_y,inv_x,inv_y,note'
const DSE_CSV_NOTE = 'inv_x=(forward_y/Ymax)*Xmax,inv_y=(forward_x/Xmax)*Ymax'

function generateCurveId(): string {
  return `curve_${Date.now()}_${Math.random().toString(36).slice(2, 9)}`
}

function roundToTwo(value: number): number {
  return Math.round(value * 100) / 100
}

function clamp(value: number, min = 0, max = 100): number {
  return Math.max(min, Math.min(max, value))
}

function formatNumber(value: number): string {
  return Number.isInteger(value) ? String(value) : roundToTwo(value).toString()
}

/**
 * Build normalized polyline points in 0-100 scale from measured points.
 * Exactly corresponds to the measured points after manual exclusion/recalculation.
 */
export function buildNormalizedPolylinePoints(
  measuredPoints: ExportMeasurementPoint[] | null | undefined,
  innerDz: number = 0.0,
  outerDz: number = 1.0
): ControllerMetaCurvePoint[] {
  if (!measuredPoints || measuredPoints.length === 0) {
    return [
      { x: 0, y: 0 },
      { x: 100, y: 100 },
    ]
  }

  // Filter valid points strictly within active deadzone range
  const inRangeValid = measuredPoints.filter(
    (p) =>
      p.valid !== false &&
      p.velocity_px_s !== null &&
      p.in_analysis_range !== false &&
      p.input >= innerDz - 1e-4 &&
      p.input <= outerDz + 1e-4
  )

  const validPoints =
    inRangeValid.length >= 2
      ? inRangeValid
      : measuredPoints.filter((p) => p.valid !== false && p.velocity_px_s !== null)

  if (validPoints.length === 0) {
    return [
      { x: 0, y: 0 },
      { x: 100, y: 100 },
    ]
  }

  // Sort strictly by input
  const sorted = [...validPoints].sort((a, b) => a.input - b.input)

  // Normalize X-axis across the actual remaining valid in-range points:
  // First valid point (e.g. 12%) maps to 0%, last valid point (e.g. 87%) maps to 100% full scale.
  const minInput = sorted[0].input
  const maxInput = sorted[sorted.length - 1].input
  const span = Math.max(0.001, maxInput - minInput)

  const velocities = sorted.map((p) => p.velocity_px_s || 0)
  const minVel = Math.min(...velocities)
  const maxVel = Math.max(...velocities)
  const vRange = Math.max(0.001, maxVel - minVel)

  return sorted.map((p, idx) => {
    let normX: number
    if (idx === 0) {
      normX = 0
    } else if (idx === sorted.length - 1) {
      normX = 100
    } else {
      normX = clamp(((p.input - minInput) / span) * 100, 0, 100)
    }

    let normY: number
    if (idx === 0) {
      normY = 0
    } else if (idx === sorted.length - 1) {
      normY = 100
    } else {
      if (p.normalized_speed !== undefined && p.normalized_speed !== null) {
        normY = clamp(p.normalized_speed * 100, 0, 100)
      } else {
        normY = clamp((((p.velocity_px_s || 0) - minVel) / vRange) * 100, 0, 100)
      }
    }

    return {
      x: roundToTwo(normX),
      y: roundToTwo(normY),
    }
  })
}

export function buildRawPolylinePoints(
  measuredPoints: ExportMeasurementPoint[] | null | undefined,
  innerDz: number,
  outerDz: number
): ControllerMetaCurvePoint[] {
  if (!measuredPoints || measuredPoints.length === 0) {
    return [
      { x: roundToTwo(innerDz * 100), y: 0 },
      { x: roundToTwo(outerDz * 100), y: 100 },
    ]
  }

  const validPoints = measuredPoints.filter((p) => p.valid !== false && p.velocity_px_s !== null)
  if (validPoints.length === 0) {
    return [
      { x: roundToTwo(innerDz * 100), y: 0 },
      { x: roundToTwo(outerDz * 100), y: 100 },
    ]
  }

  const velocities = validPoints.map((p) => p.velocity_px_s || 0)
  const minVel = Math.min(...velocities)
  const maxVel = Math.max(...velocities)
  const vRange = Math.max(0.001, maxVel - minVel)

  return validPoints.map((p) => {
    const rawX = clamp(p.input * 100, 0, 100)
    let rawY = 0
    if (p.normalized_speed !== undefined && p.normalized_speed !== null) {
      rawY = clamp(p.normalized_speed * 100, 0, 100)
    } else {
      rawY = clamp((((p.velocity_px_s || 0) - minVel) / vRange) * 100, 0, 100)
    }

    return {
      x: roundToTwo(rawX),
      y: roundToTwo(rawY),
    }
  })
}

/**
 * Build ControllerMeta curve model for a single layer.
 */
export function buildControllerMetaCurveModel(
  candidate: FitCandidate | null,
  measuredPoints: ExportMeasurementPoint[] | null | undefined,
  innerDz: number = 0.0,
  outerDz: number = 1.0,
  curveName = 'GameCurveProbe Curve',
  normalizeToFullScale = true,
  options?: {
    color?: string
    isFittedLayer?: boolean
  }
): ControllerMetaCurveModel {
  const now = new Date().toISOString()
  const innerDeadzone = normalizeToFullScale ? 0 : Math.round(Math.max(0, Math.min(100, innerDz * 100)) * 100) / 100
  const outerDeadzone = normalizeToFullScale ? 0 : Math.round(Math.max(0, Math.min(100, (1.0 - outerDz) * 100)) * 100) / 100

  if (options?.isFittedLayer) {
    // Fitted layer: Use native Bezier or clean key control points (2 to 4 points)
    const isBezier = (candidate?.type === 'bezier' || candidate?.type === 'power') && !!candidate.bezierControlPoints
    const kind: 'bezier' | 'polyline' = isBezier ? 'bezier' : 'polyline'
    const color = options?.color || '#10b981'

    const model: ControllerMetaCurveModel = {
      id: generateCurveId(),
      name: curveName,
      kind,
      color,
      visible: true,
      createdAt: now,
      updatedAt: now,
      sourceMeta: {
        kind: 'manual',
        description: `Fitted ${candidate?.name || 'Model'} from GameCurveProbe`,
      },
      innerDeadzone: 0,
      outerDeadzone: 0,
      deadzoneAdjustMode: 'compress',
    }

    if (kind === 'bezier' && candidate?.bezierControlPoints) {
      model.bezier = {
        p1: { x: roundToTwo(candidate.bezierControlPoints.p1.x), y: roundToTwo(candidate.bezierControlPoints.p1.y) },
        p2: { x: roundToTwo(candidate.bezierControlPoints.p2.x), y: roundToTwo(candidate.bezierControlPoints.p2.y) },
      }
    } else if (candidate?.keyPoints && candidate.keyPoints.length > 0) {
      model.points = candidate.keyPoints.map((p) => ({ x: roundToTwo(p.x), y: roundToTwo(p.y) }))
      model.basePoints = model.points.map((p) => ({ ...p }))
    } else if (candidate?.type === 'linear') {
      model.points = [{ x: 0, y: 0 }, { x: 100, y: 100 }]
      model.basePoints = [{ x: 0, y: 0 }, { x: 100, y: 100 }]
    } else {
      model.points = [{ x: 0, y: 0 }, { x: 100, y: 100 }]
      model.basePoints = [{ x: 0, y: 0 }, { x: 100, y: 100 }]
    }

    return model
  }

  // Measured layer or single raw layer
  const points = normalizeToFullScale
    ? buildNormalizedPolylinePoints(measuredPoints, innerDz, outerDz)
    : buildRawPolylinePoints(measuredPoints, innerDz, outerDz)

  return {
    id: generateCurveId(),
    name: curveName,
    kind: 'polyline',
    color: options?.color || '#4f8cff',
    visible: true,
    createdAt: now,
    updatedAt: now,
    sourceMeta: {
      kind: 'manual',
      description: 'Measured Points from GameCurveProbe',
    },
    innerDeadzone,
    outerDeadzone,
    deadzoneAdjustMode: 'compress',
    points: points.map((p) => ({ ...p })),
    basePoints: points.map((p) => ({ ...p })),
  }
}

/**
 * Build Multi-Layer ControllerMeta JSON (Layer 1: Measured Normalized Polyline, Layer 2: Fitted Model).
 */
export function buildMultiLayerControllerMetaJson(
  candidate: FitCandidate | null,
  measuredPoints: ExportMeasurementPoint[] | null | undefined,
  innerDz: number = 0.0,
  outerDz: number = 1.0,
  modelLabel = 'Fitted Model',
  measuredLayerName = '实测点位 (归一化)',
  fittedLayerPrefix = '拟合曲线'
): string {
  const now = new Date().toISOString()

  // Layer 1: Measured polyline (normalized points with exact sample count)
  const measuredLayer = buildControllerMetaCurveModel(
    null,
    measuredPoints,
    innerDz,
    outerDz,
    measuredLayerName,
    true,
    { color: '#4f8cff', isFittedLayer: false }
  )

  // Layer 2: Fitted model curve (Bezier control points or key piecewise/linear points)
  const fittedName = `${fittedLayerPrefix} (${modelLabel})`
  const fittedLayer = buildControllerMetaCurveModel(
    candidate,
    measuredPoints,
    innerDz,
    outerDz,
    fittedName,
    true,
    { color: '#10b981', isFittedLayer: true }
  )

  const bundle: ControllerMetaTransferBundle = {
    identifier: 'ControllerMeta',
    formatVersion: '1.0.0',
    exportKind: 'curve_transfer',
    exportTime: now,
    itemCount: 2,
    items: [
      {
        curve: measuredLayer,
        savedAt: now,
        note: 'GameCurveProbe Measured Polyline (Normalized)',
      },
      {
        curve: fittedLayer,
        savedAt: now,
        note: `GameCurveProbe Fitted Curve (${candidate?.name || modelLabel})`,
      },
    ],
  }

  return `${JSON.stringify(bundle, null, 2)}\n`
}

/**
 * Build Single-Layer ControllerMeta JSON (Raw with deadzone or fallback).
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
  const curve = buildControllerMetaCurveModel(
    candidate,
    measuredPoints,
    innerDz,
    outerDz,
    curveName,
    normalizeToFullScale
  )

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
 * Build ControllerMeta-compatible DSE CSV content (Raw Points with Deadzone).
 */
export function buildDseCsv(
  _candidate: FitCandidate | null,
  measuredPoints: ExportMeasurementPoint[] | null | undefined,
  innerDz: number = 0.0,
  outerDz: number = 1.0,
  normalizeToFullScale = true
): string {
  const points = normalizeToFullScale
    ? buildNormalizedPolylinePoints(measuredPoints, innerDz, outerDz)
    : buildRawPolylinePoints(measuredPoints, innerDz, outerDz)

  const metaComment = `# format=GameCurveProbe,inner_deadzone=${innerDz},outer_deadzone=${outerDz},normalized=${normalizeToFullScale}`

  const rows = points.map((point, index) => {
    const pointIndex = index + 1
    const forwardX = formatNumber(point.x)
    const forwardY = formatNumber(point.y)
    const invX = forwardY
    const invY = forwardX
    return `${pointIndex},${forwardX},${forwardY},${invX},${invY},${DSE_CSV_NOTE}`
  })

  return `${[metaComment, DSE_CSV_HEADER, ...rows].join('\n')}\n`
}

/**
 * Parse imported curve file (ControllerMeta multi/single-layer JSON, GameCurveProbe native JSON, or CSV).
 * Returns a reconstructed SessionResult for loading into sessionStore.
 */
export function parseExportedCurveFile(content: string, _filename?: string): SessionResult {
  const trimmed = content.trim()
  if (!trimmed) {
    throw new Error('Empty file content')
  }

  // 1. Try JSON parsing
  if (trimmed.startsWith('{') || trimmed.startsWith('[')) {
    let parsed: any
    try {
      parsed = JSON.parse(trimmed)
    } catch (e: any) {
      throw new Error(`JSON Parse Error: ${e.message}`)
    }

    // A. Native GameCurveProbe SessionResult format
    if (parsed && Array.isArray(parsed.points) && parsed.points.length > 0 && typeof parsed.points[0].input === 'number') {
      return parsed as SessionResult
    }

    // B. ControllerMeta Transfer Bundle (items or curves array)
    let candidateCurves: ControllerMetaCurveModel[] = []
    if (Array.isArray(parsed)) {
      candidateCurves = parsed.map((item: any) => item?.curve || item).filter(Boolean)
    } else if (Array.isArray(parsed.items)) {
      candidateCurves = parsed.items.map((item: any) => item?.curve || item).filter(Boolean)
    } else if (Array.isArray(parsed.curves)) {
      candidateCurves = parsed.curves.map((item: any) => item?.curve || item).filter(Boolean)
    } else if (parsed.curve && typeof parsed.curve === 'object') {
      candidateCurves = [parsed.curve]
    } else if (parsed.kind && (parsed.points || parsed.bezier)) {
      candidateCurves = [parsed]
    }

    if (candidateCurves.length > 0) {
      // Find the measured polyline curve (preferably one named "Measured" / "实测", or the first polyline with points)
      let targetCurve = candidateCurves.find(
        (c) => c.kind === 'polyline' && c.points && c.points.length > 0 && /实测|measured/i.test(c.name || '')
      )
      if (!targetCurve) {
        targetCurve = candidateCurves.find((c) => c.points && c.points.length > 0) || candidateCurves[0]
      }

      const innerDzPct = targetCurve.innerDeadzone ?? 0
      const outerDzPct = targetCurve.outerDeadzone ?? 0
      const inner_deadzone = roundToTwo(innerDzPct / 100)
      const outer_deadzone = roundToTwo(1.0 - outerDzPct / 100)

      let rawPoints: ControllerMetaCurvePoint[] = []
      if (targetCurve.points && targetCurve.points.length > 0) {
        rawPoints = targetCurve.points
      } else if (targetCurve.basePoints && targetCurve.basePoints.length > 0) {
        rawPoints = targetCurve.basePoints
      } else if (targetCurve.kind === 'bezier' && targetCurve.bezier) {
        const p1 = targetCurve.bezier.p1
        const p2 = targetCurve.bezier.p2
        for (let i = 0; i <= 20; i++) {
          const t = i / 20
          const x = (1 - t) ** 3 * 0 + 3 * (1 - t) ** 2 * t * p1.x + 3 * (1 - t) * t ** 2 * p2.x + t ** 3 * 100
          const y = (1 - t) ** 3 * 0 + 3 * (1 - t) ** 2 * t * p1.y + 3 * (1 - t) * t ** 2 * p2.y + t ** 3 * 100
          rawPoints.push({ x, y })
        }
      }

      const points: MeasurementPoint[] = rawPoints.map((pt) => {
        const input = roundToTwo(pt.x / 100)
        const normalized_speed = roundToTwo(pt.y / 100)
        const velocity_px_s = roundToTwo(normalized_speed * 1000)
        return {
          input,
          velocity_px_s,
          normalized_speed,
          stability: 1.0,
          valid: true,
          attempts: 1,
        }
      })

      return {
        schema_version: 1,
        measured_at: parsed.exportTime || new Date().toISOString(),
        points,
        config: {
          inner_deadzone,
          outer_deadzone,
          range_mode: 'active_range',
        },
      } as SessionResult
    }

    throw new Error('Unsupported JSON format: no valid points or curves found.')
  }

  // 2. Try CSV parsing
  const lines = trimmed
    .replace(/^\uFEFF/, '')
    .split(/\r?\n/)
    .map((l) => l.trim())
    .filter((l) => l.length > 0)

  if (lines.length === 0) {
    throw new Error('CSV file is empty.')
  }

  let inner_deadzone = 0.0
  let outer_deadzone = 1.0
  const dataPoints: ControllerMetaCurvePoint[] = []

  for (const line of lines) {
    if (line.startsWith('#')) {
      const innerMatch = line.match(/inner_deadzone=([0-9.]+)/i)
      const outerMatch = line.match(/outer_deadzone=([0-9.]+)/i)
      if (innerMatch) inner_deadzone = Number.parseFloat(innerMatch[1])
      if (outerMatch) outer_deadzone = Number.parseFloat(outerMatch[1])
      continue
    }

    if (line.toLowerCase().startsWith('point_index') || line.toLowerCase().startsWith('index')) {
      continue
    }

    const parts = line.split(',').map((s) => s.trim())
    if (parts.length >= 3) {
      const x = Number.parseFloat(parts[1])
      const y = Number.parseFloat(parts[2])
      if (Number.isFinite(x) && Number.isFinite(y)) {
        dataPoints.push({ x, y })
      }
    } else if (parts.length === 2) {
      const x = Number.parseFloat(parts[0])
      const y = Number.parseFloat(parts[1])
      if (Number.isFinite(x) && Number.isFinite(y)) {
        dataPoints.push({ x, y })
      }
    }
  }

  if (dataPoints.length === 0) {
    throw new Error('No valid point coordinates found in CSV.')
  }

  const maxX = Math.max(...dataPoints.map((p) => p.x), 100)
  const scale = 100 / maxX

  const points: MeasurementPoint[] = dataPoints.map((pt) => {
    const input = roundToTwo((pt.x * scale) / 100)
    const normalized_speed = roundToTwo((pt.y * scale) / 100)
    const velocity_px_s = roundToTwo(normalized_speed * 1000)
    return {
      input,
      velocity_px_s,
      normalized_speed,
      stability: 1.0,
      valid: true,
      attempts: 1,
    }
  })

  if (inner_deadzone === 0.0 && outer_deadzone === 1.0 && points.length > 2) {
    if (points[0].input > 0) {
      inner_deadzone = points[0].input
    }
    if (points[points.length - 1].input < 1.0 && points[points.length - 1].input > 0.5) {
      outer_deadzone = points[points.length - 1].input
    }
  }

  return {
    schema_version: 1,
    measured_at: new Date().toISOString(),
    points,
    config: {
      inner_deadzone: roundToTwo(inner_deadzone),
      outer_deadzone: roundToTwo(outer_deadzone),
      range_mode: 'active_range',
    },
  } as SessionResult
}
