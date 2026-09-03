import type { MeasurementPoint } from '../types/api'

export interface CurveSeriesData {
  name: string
  data: Array<[number, number | null]>
  imported: boolean
}

export function buildVelocitySeries(
  measured: MeasurementPoint[],
  imported: MeasurementPoint[] = [],
): CurveSeriesData[] {
  const series: CurveSeriesData[] = [{
    name: '实测速度 (px/s)',
    data: measured.map((point) => [point.input, point.velocity_px_s]),
    imported: false,
  }]
  if (imported.length > 0) {
    series.push({
      name: '导入速度 (px/s)',
      data: imported.map((point) => [point.input, point.velocity_px_s]),
      imported: true,
    })
  }
  return series
}
