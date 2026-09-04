/**
 * Gamepad Response Curve Fitting and Estimation Engine
 * 
 * Fits measured response curve data points against 5 candidate models:
 * 1. linear: y = kx + b
 * 2. power: y = x^gamma
 * 3. piecewise1: 1-breakpoint piecewise linear (Outer Threshold Acceleration)
 * 4. piecewise2: 2-breakpoint piecewise linear (3 segments)
 * 5. bezier: monotonic cubic Bezier curve (0,0) -> (1,1)
 *
 * Includes MAD-based robust outlier rejection and Bayesian Information Criterion (BIC)
 * model evaluation to prevent overfitting.
 */

export type FitModelType = 'linear' | 'power' | 'piecewise1' | 'piecewise2' | 'bezier'

export interface FitCandidate {
  type: FitModelType
  name: string
  nrmse: number
  r2: number
  bic: number
  confidence: number
  params: Record<string, number | string>
  breakpoints?: number[] // Physical input coordinates (e.g. 0.94)
  curvePoints: [number, number][] // [x_input, y_speed_px_s] 100 smooth interpolation points
}

export interface CurveFitReport {
  best: FitCandidate
  candidates: Record<FitModelType, FitCandidate>
  outlierInputs: number[] // Physical input coordinates flagged as outliers
}

interface RawPoint {
  input: number
  velocity_px_s: number | null
  valid: boolean
}

interface Point2D {
  u: number // normalized input [0, 1]
  w: number // normalized velocity [0, 1]
  xOrig: number
  vOrig: number
}

// -------------------------------------------------------------
// Outlier Rejection via Isolated Neighbor Deviation on Raw Velocities
// -------------------------------------------------------------
function detectOutliers(velocities: number[]): number[] {
  const n = velocities.length
  if (n < 5) return []

  // Estimate the local noise/step scale from adjacent differences. Keep the
  // floor relative to the observed signal so low-speed captures are not
  // governed by an arbitrary px/s constant.
  const diffs: number[] = []
  for (let i = 1; i < n; i++) {
    diffs.push(Math.abs(velocities[i] - velocities[i - 1]))
  }
  diffs.sort((a, b) => a - b)
  const medianStep = diffs[Math.floor(diffs.length / 2)]
  const sortedVelocities = [...velocities].sort((a, b) => a - b)
  const signalSpan = sortedVelocities[n - 1] - sortedVelocities[0]
  const adaptiveFloor = Math.max(Number.EPSILON, signalSpan * 0.01)
  const minThreshold = Math.max(adaptiveFloor, medianStep * 3.5)

  const outlierIndices: number[] = []

  // Check interior points
  for (let i = 1; i < n - 1; i++) {
    const vPrev = velocities[i - 1]
    const vCurr = velocities[i]
    const vNext = velocities[i + 1]

    const interpolated = (vPrev + vNext) / 2
    const isolatedDev = Math.abs(vCurr - interpolated)
    const neighborDiff = Math.abs(vNext - vPrev)

    // An isolated glitch spike/drop deviates heavily from both neighbors
    // while the neighbors themselves form a consistent trend.
    if (isolatedDev > minThreshold && isolatedDev > neighborDiff * 1.5) {
      outlierIndices.push(i)
    }
  }

  // Check boundary points against linear extrapolation
  if (n >= 4) {
    const extrap0 = 2 * velocities[1] - velocities[2]
    const dev0 = Math.abs(velocities[0] - extrap0)
    const step0 = Math.abs(velocities[2] - velocities[1])
    if (dev0 > minThreshold && dev0 > step0 * 3.0) {
      outlierIndices.push(0)
    }

    const extrapLast = 2 * velocities[n - 2] - velocities[n - 3]
    const devLast = Math.abs(velocities[n - 1] - extrapLast)
    const stepLast = Math.abs(velocities[n - 2] - velocities[n - 3])
    if (devLast > minThreshold && devLast > stepLast * 3.0) {
      outlierIndices.push(n - 1)
    }
  }

  return outlierIndices
}

// -------------------------------------------------------------
// Statistical Metrics Helpers
// -------------------------------------------------------------
function computeMetrics(
  actual: number[],
  predicted: number[],
  paramCount: number
): { mse: number; nrmse: number; r2: number; bic: number; confidence: number } {
  const n = actual.length
  if (n === 0) return { mse: 0, nrmse: 0, r2: 1, bic: 0, confidence: 1 }

  let sse = 0
  let actualSum = 0
  for (let i = 0; i < n; i++) {
    sse += (actual[i] - predicted[i]) ** 2
    actualSum += actual[i]
  }
  const mean = actualSum / n
  let sst = 0
  for (let i = 0; i < n; i++) {
    sst += (actual[i] - mean) ** 2
  }

  const mse = sse / n
  const rmse = Math.sqrt(mse)
  const range = 1.0 // since values are normalized [0, 1]
  const nrmse = Math.min(1.0, rmse / range)
  const r2 = sst > 1e-8 ? Math.max(0, 1 - sse / sst) : 1.0

  // BIC = n * ln(MSE + eps) + k * ln(n)
  const bic = n * Math.log(mse + 1e-8) + paramCount * Math.log(n)
  const confidence = Math.max(0, Math.min(1, (1 - nrmse) * (0.5 + 0.5 * r2)))

  return { mse, nrmse, r2, bic, confidence }
}

// -------------------------------------------------------------
// Model 1: Linear Fit
// -------------------------------------------------------------
function fitLinear(
  inliers: Point2D[],
  vMin: number,
  vRange: number,
  innerDz: number,
  dzRange: number
): FitCandidate {
  const n = inliers.length
  let sumU = 0
  let sumW = 0
  let sumUW = 0
  let sumUU = 0

  for (const pt of inliers) {
    sumU += pt.u
    sumW += pt.w
    sumUW += pt.u * pt.w
    sumUU += pt.u * pt.u
  }

  const denom = n * sumUU - sumU * sumU
  const slope = denom !== 0 ? (n * sumUW - sumU * sumW) / denom : 1.0
  const intercept = (sumW - slope * sumU) / n

  const predicted = inliers.map((pt) => Math.max(0, Math.min(1, slope * pt.u + intercept)))
  const metrics = computeMetrics(inliers.map((pt) => pt.w), predicted, 2)

  // Generate 100 interpolation points
  const curvePoints: [number, number][] = []
  for (let i = 0; i < 100; i++) {
    const u = i / 99
    const w = Math.max(0, Math.min(1, slope * u + intercept))
    const x = innerDz + u * dzRange
    const y = vMin + w * vRange
    curvePoints.push([Math.round(x * 1000) / 1000, Math.round(y * 10) / 10])
  }

  return {
    type: 'linear',
    name: '纯线性 (Linear)',
    ...metrics,
    params: {
      slope: Math.round(slope * 1000) / 1000,
      intercept: Math.round(intercept * 1000) / 1000,
      physicalSlope: Math.round(((slope * vRange) / dzRange) * 10) / 10,
    },
    curvePoints,
  }
}

// -------------------------------------------------------------
// Model 2: Power Curve (y = x^gamma)
// -------------------------------------------------------------
function fitPower(
  inliers: Point2D[],
  vMin: number,
  vRange: number,
  innerDz: number,
  dzRange: number
): FitCandidate {
  let bestGamma = 1.0
  let bestSse = Infinity

  // Grid search gamma in [0.25, 4.0]
  for (let g = 0.25; g <= 4.0; g += 0.05) {
    let sse = 0
    for (const pt of inliers) {
      const pred = Math.pow(Math.max(0, pt.u), g)
      sse += (pt.w - pred) ** 2
    }
    if (sse < bestSse) {
      bestSse = sse
      bestGamma = g
    }
  }

  // Refine around bestGamma
  const startG = Math.max(0.2, bestGamma - 0.05)
  const endG = Math.min(4.5, bestGamma + 0.05)
  for (let g = startG; g <= endG; g += 0.01) {
    let sse = 0
    for (const pt of inliers) {
      const pred = Math.pow(Math.max(0, pt.u), g)
      sse += (pt.w - pred) ** 2
    }
    if (sse < bestSse) {
      bestSse = sse
      bestGamma = g
    }
  }

  const predicted = inliers.map((pt) => Math.pow(Math.max(0, pt.u), bestGamma))
  const metrics = computeMetrics(inliers.map((pt) => pt.w), predicted, 1)

  const curvePoints: [number, number][] = []
  for (let i = 0; i < 100; i++) {
    const u = i / 99
    const w = Math.pow(u, bestGamma)
    const x = innerDz + u * dzRange
    const y = vMin + w * vRange
    curvePoints.push([Math.round(x * 1000) / 1000, Math.round(y * 10) / 10])
  }

  return {
    type: 'power',
    name: '幂函数凹/凸曲线 (Power)',
    ...metrics,
    params: {
      gamma: Math.round(bestGamma * 100) / 100,
      shape: bestGamma > 1.05 ? '下凹加速型' : bestGamma < 0.95 ? '上凸灵敏型' : '接近线性',
    },
    curvePoints,
  }
}

// -------------------------------------------------------------
// Model 3: 1-Breakpoint Piecewise Linear (Outer Threshold Boost)
// -------------------------------------------------------------
function fitPiecewise1(
  inliers: Point2D[],
  vMin: number,
  vRange: number,
  innerDz: number,
  dzRange: number
): FitCandidate {
  const n = inliers.length
  let bestUb = 0.8
  let bestK1 = 1.0
  let bestK2 = 1.0
  let bestSse = Infinity

  // Candidate breakpoints from index 2 to n - 3
  for (let idx = 2; idx <= n - 3; idx++) {
    const ub = inliers[idx].u
    if (ub < 0.15 || ub > 0.95) continue

    const left = inliers.slice(0, idx + 1)
    const right = inliers.slice(idx)

    // Left segment: w = k1 * u (pass through 0,0)
    let sumULeft2 = 0
    let sumUWLeft = 0
    for (const pt of left) {
      sumULeft2 += pt.u * pt.u
      sumUWLeft += pt.u * pt.w
    }
    const k1 = sumULeft2 > 1e-6 ? sumUWLeft / sumULeft2 : 1.0
    const wb = k1 * ub

    // Right segment: w - wb = k2 * (u - ub)
    let sumURight2 = 0
    let sumUWRight = 0
    for (const pt of right) {
      const du = pt.u - ub
      const dw = pt.w - wb
      sumURight2 += du * du
      sumUWRight += du * dw
    }
    const k2 = sumURight2 > 1e-6 ? Math.max(0, sumUWRight / sumURight2) : k1

    let sse = 0
    for (const pt of inliers) {
      const pred = pt.u <= ub ? k1 * pt.u : wb + k2 * (pt.u - ub)
      sse += (pt.w - pred) ** 2
    }

    if (sse < bestSse) {
      bestSse = sse
      bestUb = ub
      bestK1 = k1
      bestK2 = k2
    }
  }

  const wb = bestK1 * bestUb
  const evalPiecewise = (u: number) =>
    Math.max(0, Math.min(1, u <= bestUb ? bestK1 * u : wb + bestK2 * (u - bestUb)))

  const predicted = inliers.map((pt) => evalPiecewise(pt.u))
  const metrics = computeMetrics(inliers.map((pt) => pt.w), predicted, 3)

  const physBreakpoint = innerDz + bestUb * dzRange
  const boostRatio = Math.max(0.1, bestK2 / Math.max(0.01, bestK1))

  const curvePoints: [number, number][] = []
  for (let i = 0; i < 100; i++) {
    const u = i / 99
    const w = evalPiecewise(u)
    const x = innerDz + u * dzRange
    const y = vMin + w * vRange
    curvePoints.push([Math.round(x * 1000) / 1000, Math.round(y * 10) / 10])
  }

  return {
    type: 'piecewise1',
    name: '1点折线 (末端额外加速)',
    ...metrics,
    breakpoints: [Math.round(physBreakpoint * 1000) / 1000],
    params: {
      accelThreshold: `${(physBreakpoint * 100).toFixed(1)}%`,
      boostRatio: Math.round(boostRatio * 10) / 10,
      baseSlope: Math.round(((bestK1 * vRange) / dzRange) * 10) / 10,
      accelSlope: Math.round(((bestK2 * vRange) / dzRange) * 10) / 10,
    },
    curvePoints,
  }
}

// -------------------------------------------------------------
// Model 4: 2-Breakpoint Piecewise Linear (3 segments)
// -------------------------------------------------------------
function fitPiecewise2(
  inliers: Point2D[],
  vMin: number,
  vRange: number,
  innerDz: number,
  dzRange: number
): FitCandidate {
  const n = inliers.length
  let bestUb1 = 0.3
  let bestUb2 = 0.8
  let bestK1 = 1.0, bestK2 = 1.0, bestK3 = 1.0
  let bestSse = Infinity

  const step = Math.max(1, Math.floor(n / 10))
  for (let i = 2; i < n - 4; i += step) {
    const ub1 = inliers[i].u
    if (ub1 < 0.1 || ub1 > 0.6) continue

    for (let j = i + 2; j < n - 2; j += step) {
      const ub2 = inliers[j].u
      if (ub2 - ub1 < 0.1 || ub2 > 0.95) continue

      // Seg 1: 0 -> ub1
      const seg1 = inliers.slice(0, i + 1)
      let sumU1_2 = 0, sumUW1 = 0
      for (const pt of seg1) {
        sumU1_2 += pt.u * pt.u
        sumUW1 += pt.u * pt.w
      }
      const k1 = sumU1_2 > 1e-6 ? sumUW1 / sumU1_2 : 1.0
      const w1 = k1 * ub1

      // Seg 2: ub1 -> ub2
      const seg2 = inliers.slice(i, j + 1)
      let sumU2_2 = 0, sumUW2 = 0
      for (const pt of seg2) {
        const du = pt.u - ub1
        const dw = pt.w - w1
        sumU2_2 += du * du
        sumUW2 += du * dw
      }
      const k2 = sumU2_2 > 1e-6 ? Math.max(0, sumUW2 / sumU2_2) : k1
      const w2 = w1 + k2 * (ub2 - ub1)

      // Seg 3: ub2 -> 1
      const seg3 = inliers.slice(j)
      let sumU3_2 = 0, sumUW3 = 0
      for (const pt of seg3) {
        const du = pt.u - ub2
        const dw = pt.w - w2
        sumU3_2 += du * du
        sumUW3 += du * dw
      }
      const k3 = sumU3_2 > 1e-6 ? Math.max(0, sumUW3 / sumU3_2) : k2

      let sse = 0
      for (const pt of inliers) {
        let pred = 0
        if (pt.u <= ub1) pred = k1 * pt.u
        else if (pt.u <= ub2) pred = w1 + k2 * (pt.u - ub1)
        else pred = w2 + k3 * (pt.u - ub2)
        sse += (pt.w - pred) ** 2
      }

      if (sse < bestSse) {
        bestSse = sse
        bestUb1 = ub1
        bestUb2 = ub2
        bestK1 = k1
        bestK2 = k2
        bestK3 = k3
      }
    }
  }

  const w1 = bestK1 * bestUb1
  const w2 = w1 + bestK2 * (bestUb2 - bestUb1)
  const evalPiecewise2 = (u: number) => {
    let val: number
    if (u <= bestUb1) val = bestK1 * u
    else if (u <= bestUb2) val = w1 + bestK2 * (u - bestUb1)
    else val = w2 + bestK3 * (u - bestUb2)
    return Math.max(0, Math.min(1, val))
  }

  const predicted = inliers.map((pt) => evalPiecewise2(pt.u))
  const metrics = computeMetrics(inliers.map((pt) => pt.w), predicted, 5)

  const bp1 = innerDz + bestUb1 * dzRange
  const bp2 = innerDz + bestUb2 * dzRange

  const curvePoints: [number, number][] = []
  for (let i = 0; i < 100; i++) {
    const u = i / 99
    const w = evalPiecewise2(u)
    const x = innerDz + u * dzRange
    const y = vMin + w * vRange
    curvePoints.push([Math.round(x * 1000) / 1000, Math.round(y * 10) / 10])
  }

  return {
    type: 'piecewise2',
    name: '2点折线 (三段式曲线)',
    ...metrics,
    breakpoints: [Math.round(bp1 * 1000) / 1000, Math.round(bp2 * 1000) / 1000],
    params: {
      breakpoint1: `${(bp1 * 100).toFixed(1)}%`,
      breakpoint2: `${(bp2 * 100).toFixed(1)}%`,
      k1: Math.round(bestK1 * 100) / 100,
      k2: Math.round(bestK2 * 100) / 100,
      k3: Math.round(bestK3 * 100) / 100,
    },
    curvePoints,
  }
}

// -------------------------------------------------------------
// Model 5: Cubic Bézier Curve
// -------------------------------------------------------------
function fitCubicBezier(
  inliers: Point2D[],
  vMin: number,
  vRange: number,
  innerDz: number,
  dzRange: number
): FitCandidate {
  // Monotonic cubic bezier: P0=(0,0), P1=(x1, y1), P2=(x2, y2), P3=(1,1)
  // Grid search control points with monotonicity constraint: 0 <= x1 <= x2 <= 1, 0 <= y1 <= y2 <= 1
  let bestP1 = [0.33, 0.33]
  let bestP2 = [0.66, 0.66]
  let bestSse = Infinity

  const sampleBezierY = (u: number, p1x: number, p1y: number, p2x: number, p2y: number): number => {
    // Solve for parameter t such that B_x(t) = u using binary search
    let low = 0
    let high = 1
    let t = u
    for (let iter = 0; iter < 10; iter++) {
      t = (low + high) / 2
      const omt = 1 - t
      const bx = 3 * omt * omt * t * p1x + 3 * omt * t * t * p2x + t * t * t
      if (bx < u) low = t
      else high = t
    }
    const omt = 1 - t
    return 3 * omt * omt * t * p1y + 3 * omt * t * t * p2y + t * t * t
  }

  // Fast coarse grid
  const steps = [0.15, 0.35, 0.55, 0.75, 0.85]
  for (const p1y of steps) {
    for (const p2y of steps) {
      if (p1y > p2y) continue
      const p1x = 0.35
      const p2x = 0.65

      let sse = 0
      for (const pt of inliers) {
        const pred = sampleBezierY(pt.u, p1x, p1y, p2x, p2y)
        sse += (pt.w - pred) ** 2
      }

      if (sse < bestSse) {
        bestSse = sse
        bestP1 = [p1x, p1y]
        bestP2 = [p2x, p2y]
      }
    }
  }

  const predicted = inliers.map((pt) =>
    sampleBezierY(pt.u, bestP1[0], bestP1[1], bestP2[0], bestP2[1])
  )
  const metrics = computeMetrics(inliers.map((pt) => pt.w), predicted, 4)

  const curvePoints: [number, number][] = []
  for (let i = 0; i < 100; i++) {
    const u = i / 99
    const w = sampleBezierY(u, bestP1[0], bestP1[1], bestP2[0], bestP2[1])
    const x = innerDz + u * dzRange
    const y = vMin + Math.max(0, Math.min(1, w)) * vRange
    curvePoints.push([Math.round(x * 1000) / 1000, Math.round(y * 10) / 10])
  }

  return {
    type: 'bezier',
    name: '三次贝塞尔曲线 (Bézier)',
    ...metrics,
    params: {
      p1: `(${bestP1[0].toFixed(2)}, ${bestP1[1].toFixed(2)})`,
      p2: `(${bestP2[0].toFixed(2)}, ${bestP2[1].toFixed(2)})`,
    },
    curvePoints,
  }
}

// -------------------------------------------------------------
// Main API: fitResponseCurve
// -------------------------------------------------------------
export function fitResponseCurve(
  points: RawPoint[],
  innerDz: number = 0.0,
  outerDz: number = 1.0
): CurveFitReport | null {
  const inner = Math.max(0, Math.min(1, innerDz))
  const outer = Math.max(0, Math.min(1, outerDz))
  const dzRange = outer - inner
  if (dzRange < 0.02) return null

  // Filter valid points in deadzone range
  const validInRange = points.filter(
    (p) => p.valid && p.velocity_px_s !== null && p.input >= inner - 1e-4 && p.input <= outer + 1e-4
  )

  if (validInRange.length < 4) return null

  // Sort by input
  const sorted = [...validInRange].sort((a, b) => a.input - b.input)
  const rawVelocities = sorted.map((p) => p.velocity_px_s!)

  // 1. Detect outliers directly on RAW velocities before normalization
  const outlierIndices = detectOutliers(rawVelocities)
  const outlierSet = new Set(outlierIndices)
  const inlierPoints = sorted.filter((_, idx) => !outlierSet.has(idx))
  const activeInliersRaw = inlierPoints.length >= 4 ? inlierPoints : sorted
  const outlierInputs = outlierIndices.map((idx) => sorted[idx].input)

  // 2. Compute vMin and vMax ONLY on inliers
  const inlierVelocities = activeInliersRaw.map((p) => p.velocity_px_s!)
  const vMin = Math.min(...inlierVelocities)
  const vMax = Math.max(...inlierVelocities)
  const vRange = vMax - vMin
  if (vRange <= 1e-6) return null

  // 3. Map inliers to normalized 2D points [0, 1]
  const activeInliers: Point2D[] = activeInliersRaw.map((p) => ({
    u: Math.max(0, Math.min(1, (p.input - inner) / dzRange)),
    w: Math.max(0, Math.min(1, (p.velocity_px_s! - vMin) / vRange)),
    xOrig: p.input,
    vOrig: p.velocity_px_s!,
  }))

  // Fit all 5 candidate models
  const linearCandidate = fitLinear(activeInliers, vMin, vRange, inner, dzRange)
  const powerCandidate = fitPower(activeInliers, vMin, vRange, inner, dzRange)
  const piecewise1Candidate = fitPiecewise1(activeInliers, vMin, vRange, inner, dzRange)
  const piecewise2Candidate = fitPiecewise2(activeInliers, vMin, vRange, inner, dzRange)
  const bezierCandidate = fitCubicBezier(activeInliers, vMin, vRange, inner, dzRange)

  const candidates: Record<FitModelType, FitCandidate> = {
    linear: linearCandidate,
    power: powerCandidate,
    piecewise1: piecewise1Candidate,
    piecewise2: piecewise2Candidate,
    bezier: bezierCandidate,
  }

  // Model Selection via BIC (lower is better)
  const candidateList = Object.values(candidates)
  candidateList.sort((a, b) => a.bic - b.bic)
  let best = candidateList[0]

  // Occam's razor: If linear fit is already exceptionally high (R^2 > 0.98, NRMSE < 0.05),
  // and power exponent is nearly 1.0 (|gamma - 1| < 0.08), prefer the simpler linear baseline.
  const powerGamma = Number(powerCandidate.params.gamma) || 1.0
  if (
    linearCandidate.r2 > 0.98 &&
    linearCandidate.nrmse < 0.05 &&
    Math.abs(powerGamma - 1.0) < 0.08 &&
    (best.type === 'power' || best.type === 'bezier')
  ) {
    best = linearCandidate
  }

  return {
    best,
    candidates,
    outlierInputs,
  }
}
