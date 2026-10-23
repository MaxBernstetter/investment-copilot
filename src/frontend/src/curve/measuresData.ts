import type { components } from '../api/schema'
import { EMPTY, formatBp } from '../format'

export type MeasurePoint = components['schemas']['MeasurePoint']
export type MeasureKey = 'spread_2y_10y' | 'spread_3m_10y' | 'curvature_2y_5y_10y'

/** Card labels of the measures, shared by the curve view and the time series view (#33). */
export const MEASURE_LABEL: Record<MeasureKey, string> = {
  spread_2y_10y: '2Y–10Y spread',
  spread_3m_10y: '3M–10Y spread',
  curvature_2y_5y_10y: '2Y–5Y–10Y curvature',
}

/** The definition of each measure, shown in its info tooltip. */
export const MEASURE_HELP: Record<MeasureKey, string> = {
  spread_2y_10y:
    '10Y yield minus 2Y yield, in basis points. Also called the slope. Below zero the curve is inverted.',
  spread_3m_10y:
    '10Y yield minus 3M yield, in basis points. Compares the long end with the money-market end of the curve.',
  curvature_2y_5y_10y:
    '2 × 5Y \u2212 2Y \u2212 10Y, in basis points. Positive means a humped belly: 5Y is above the average of 2Y and 10Y. Negative means a sagging belly.',
}

/** The input maturities of each measure, in 3M, 2Y, 5Y, 10Y order. */
export const MEASURE_INPUTS: Record<MeasureKey, readonly string[]> = {
  spread_2y_10y: ['2Y', '10Y'],
  spread_3m_10y: ['3M', '10Y'],
  curvature_2y_5y_10y: ['2Y', '5Y', '10Y'],
}

/** "5Y", "2Y or 10Y", "3M, 2Y or 10Y". */
export function listWithOr(items: readonly string[]): string {
  if (items.length <= 1) return items.join('')
  return `${items.slice(0, -1).join(', ')} or ${items[items.length - 1]}`
}

/** The measure in signed bp (formatBp), or EMPTY when there is no point or the value is null. */
export function measureValue(point: MeasurePoint | undefined, key: MeasureKey): string {
  const value = point?.[key]
  return value === null || value === undefined ? EMPTY : formatBp(value)
}

/** The dimmed hint under a measure card (design guidelines C5). */
export function measureHint(point: MeasurePoint | undefined, key: MeasureKey): string | undefined {
  if (point === undefined) return 'Not available'
  const inputs = MEASURE_INPUTS[key]
  if (point[key] === null) {
    const absent = point.missing.filter((maturity) => inputs.includes(maturity))
    return absent.length > 0 ? `No ${listWithOr(absent)} value` : 'Not available'
  }
  const flagged = point.quality.flagged.filter((maturity) => inputs.includes(maturity))
  if (flagged.length === 1) return `Input flagged: ${flagged[0]}`
  if (flagged.length > 1) return `Inputs flagged: ${flagged.join(', ')}`
  return undefined
}
