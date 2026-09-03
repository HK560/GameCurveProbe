import type { MeasurementPoint } from '../types/api'
import { t } from './i18n'

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
    name: t('series_measured'),
    data: measured.map((point) => [point.input, point.velocity_px_s]),
    imported: false,
  }]
  if (imported.length > 0) {
    series.push({
      name: t('series_imported'),
      data: imported.map((point) => [point.input, point.velocity_px_s]),
      imported: true,
    })
  }
  return series
}
