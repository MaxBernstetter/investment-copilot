import type { components } from '../api/schema'

export type SeriesPoint = components['schemas']['SeriesPoint']

/** The 11 tenors of the ECB grid, shortest first. */
export const MATURITIES = [
  '3M',
  '6M',
  '1Y',
  '2Y',
  '3Y',
  '5Y',
  '7Y',
  '10Y',
  '15Y',
  '20Y',
  '30Y',
] as const

const DAY_MS = 24 * 60 * 60 * 1000

/** Chart rows in valid-date order, as the API returns them. */
export function seriesChart(points: SeriesPoint[]): { valid_date: string; value: number }[] {
  return points.map(({ valid_date, value }) => ({ valid_date, value }))
}

/** The last 365 days up to `today`, as ISO dates (UTC). */
export function defaultRange(today: Date): { from: string; to: string } {
  const to = today.toISOString().slice(0, 10)
  const from = new Date(today.getTime() - 365 * DAY_MS).toISOString().slice(0, 10)
  return { from, to }
}

export type SeriesStats = {
  last: number | undefined
  min: number | undefined
  max: number | undefined
  /** First-to-last change in basis points, or undefined when fewer than two points. */
  changeBp: number | undefined
}

/** Summary figures for a time series in valid-date order. */
export function seriesStats(points: SeriesPoint[]): SeriesStats {
  if (points.length === 0) {
    return { last: undefined, min: undefined, max: undefined, changeBp: undefined }
  }
  const values = points.map((point) => point.value)
  const first = values[0]
  const last = values[values.length - 1]
  return {
    last,
    min: Math.min(...values),
    max: Math.max(...values),
    changeBp: points.length >= 2 ? Math.round((last - first) * 1000) / 10 : undefined,
  }
}

/** Number of values with an info or warn flag. */
export function flaggedCount(points: SeriesPoint[]): number {
  return points.filter((point) => point.quality.status === 'info' || point.quality.status === 'warn').length
}
