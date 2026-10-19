import type { components } from '../api/schema'

export type CurvePoint = components['schemas']['CurvePoint']

/** Chart series in grid order (the order the API returns); a null value becomes a gap. */
export function chartSeries(points: CurvePoint[]): { x: string[]; y: (number | null)[] } {
  return {
    x: points.map((point) => point.maturity),
    y: points.map((point) => point.value),
  }
}

/** Maturities on the grid without a published value as of the answer's knowledge time. */
export function missingMaturities(points: CurvePoint[]): string[] {
  return points.filter((point) => point.value === null).map((point) => point.maturity)
}
