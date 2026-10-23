import { MEASURE_INPUTS, MEASURE_LABEL, type MeasureKey, type MeasurePoint } from '../curve/measuresData'
import { MATURITIES, statsOf, type SeriesStats } from './seriesData'

const MEASURE_KEYS: MeasureKey[] = ['spread_2y_10y', 'spread_3m_10y', 'curvature_2y_5y_10y']

export const MEASURES: { key: MeasureKey; label: string }[] = MEASURE_KEYS.map((key) => ({
  key,
  label: MEASURE_LABEL[key],
}))

/** What the Time series view shows: one maturity yield, or one measure. */
export type SeriesChoice = { kind: 'yield'; maturity: string } | { kind: 'measure'; key: MeasureKey }

const DEFAULT_CHOICE: SeriesChoice = { kind: 'yield', maturity: '10Y' }

export function choiceValue(choice: SeriesChoice): string {
  return choice.kind === 'yield' ? `yield:${choice.maturity}` : `measure:${choice.key}`
}

/** The choice for a select value; anything unknown falls back to the 10Y yield. */
export function parseChoice(value: string): SeriesChoice {
  const parts = value.split(':')
  if (parts.length !== 2) return DEFAULT_CHOICE
  const [kind, id] = parts
  if (kind === 'yield' && (MATURITIES as readonly string[]).includes(id)) {
    return { kind: 'yield', maturity: id }
  }
  const measure = MEASURE_KEYS.find((key) => key === id)
  if (kind === 'measure' && measure !== undefined) return { kind: 'measure', key: measure }
  return DEFAULT_CHOICE
}

/** The keys that are differences of two yields, so they can go below zero. */
export type SpreadKey = 'spread_2y_10y' | 'spread_3m_10y'

export function isSpread(key: MeasureKey): key is SpreadKey {
  return key !== 'curvature_2y_5y_10y'
}

export type MeasureRow = { valid_date: string; value: number | null }

/** Chart and table rows for one measure in valid-date order; null stays null, so the chart shows a gap. */
export function measureRows(points: MeasurePoint[], key: MeasureKey): MeasureRow[] {
  return points.map((point) => ({ valid_date: point.valid_date, value: point[key] ?? null }))
}

/** Last, min, max and change in bp over the non-null values of a measure (already in bp). */
export function measureStats(points: MeasurePoint[], key: MeasureKey): SeriesStats {
  return statsOf(
    points.map((point) => point[key] ?? null),
    1,
  )
}

export type InvertedCount = { inverted: number; total: number }

/**
 * Days with a spread value below zero, out of the days with a value. Counts the
 * spread's own value, not the API `inverted` flag, which is the 2Y–10Y slope only.
 */
export function invertedDays(points: MeasurePoint[], key: SpreadKey): InvertedCount {
  const values = points.map((point) => point[key] ?? null).filter((value): value is number => value !== null)
  return { inverted: values.filter((value) => value < 0).length, total: values.length }
}

/** "Inverted on 2 of 5 days", "Inverted on 0 of 1 day". */
export function invertedHint({ inverted, total }: InvertedCount): string {
  return `Inverted on ${inverted} of ${total} ${total === 1 ? 'day' : 'days'}`
}

/** The measure's own inputs that carry a warn or info flag on this day. */
export function measureFlagged(point: MeasurePoint, key: MeasureKey): string[] {
  const inputs = MEASURE_INPUTS[key]
  return point.quality.flagged.filter((maturity) => inputs.includes(maturity))
}

/** Days with no value for the measure: the chart shows these as gaps. */
export function gapDays(points: MeasurePoint[], key: MeasureKey): number {
  return points.filter((point) => point[key] === null || point[key] === undefined).length
}

/** Days whose measure has a flagged input. */
export function flaggedMeasureDays(points: MeasurePoint[], key: MeasureKey): number {
  return points.filter((point) => measureFlagged(point, key).length > 0).length
}

/** The valid date of the last day with a value, or undefined when no day has one. */
export function lastValueDate(points: MeasurePoint[], key: MeasureKey): string | undefined {
  const withValue = points.filter((point) => point[key] !== null && point[key] !== undefined)
  return withValue[withValue.length - 1]?.valid_date
}

/** "2Y and 10Y values", "2Y, 5Y and 10Y values": the inputs a measure needs, for the empty state. */
export function measureInputsText(key: MeasureKey): string {
  const inputs = MEASURE_INPUTS[key]
  const head = inputs.slice(0, -1).join(', ')
  return `${head ? `${head} and ` : ''}${inputs[inputs.length - 1]} values`
}
