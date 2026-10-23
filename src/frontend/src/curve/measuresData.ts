import type { components } from '../api/schema'
import { EMPTY, formatBp } from '../format'

export type MeasurePoint = components['schemas']['MeasurePoint']
export type MeasureKey = 'spread_2y_10y' | 'spread_3m_10y' | 'curvature_2y_5y_10y'

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
