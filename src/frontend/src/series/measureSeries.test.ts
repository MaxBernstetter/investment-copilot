import { describe, expect, it } from 'vitest'
import type { MeasurePoint } from '../curve/measuresData'
import {
  choiceValue,
  invertedDays,
  invertedHint,
  isSpread,
  MEASURES,
  measureFlagged,
  measureRows,
  measureStats,
  parseChoice,
} from './measureSeries'

const point = (valid_date: string, overrides: Partial<MeasurePoint> = {}): MeasurePoint => ({
  valid_date,
  spread_2y_10y: 50,
  spread_3m_10y: 70,
  curvature_2y_5y_10y: -10,
  inverted: false,
  inputs: [],
  missing: [],
  quality: { status: 'passed', flagged: [] },
  ...overrides,
})

describe('measureSeries', () => {
  it('labels the three measures as the curve view cards do', () => {
    expect(MEASURES.map((measure) => measure.label)).toEqual([
      '2Y–10Y spread',
      '3M–10Y spread',
      '2Y–5Y–10Y curvature',
    ])
  })

  it('round-trips a choice through its select value', () => {
    expect(choiceValue({ kind: 'yield', maturity: '10Y' })).toBe('yield:10Y')
    expect(choiceValue({ kind: 'measure', key: 'spread_2y_10y' })).toBe('measure:spread_2y_10y')
    expect(parseChoice('yield:2Y')).toEqual({ kind: 'yield', maturity: '2Y' })
    const curvature = parseChoice('measure:curvature_2y_5y_10y')
    expect(curvature.kind).toBe('measure')
    expect(choiceValue(curvature)).toBe('measure:curvature_2y_5y_10y')
  })

  it('falls back to the 10Y yield on bad input', () => {
    expect(parseChoice('')).toEqual({ kind: 'yield', maturity: '10Y' })
    expect(parseChoice('yield:4Y')).toEqual({ kind: 'yield', maturity: '10Y' })
    expect(parseChoice('measure:unknown')).toEqual({ kind: 'yield', maturity: '10Y' })
    expect(parseChoice('10Y')).toEqual({ kind: 'yield', maturity: '10Y' })
  })

  it('marks only the two spreads as spreads', () => {
    expect(isSpread('spread_2y_10y')).toBe(true)
    expect(isSpread('spread_3m_10y')).toBe(true)
    expect(isSpread('curvature_2y_5y_10y')).toBe(false)
  })

  it('keeps null values as null rows, so the chart shows a gap', () => {
    const rows = measureRows([point('2026-10-01'), point('2026-10-02', { spread_2y_10y: null })], 'spread_2y_10y')
    expect(rows).toEqual([
      { valid_date: '2026-10-01', value: 50 },
      { valid_date: '2026-10-02', value: null },
    ])
  })

  it('stats use non-null values only, with nulls at the ends and in the middle', () => {
    const points = [
      point('2026-10-01', { spread_2y_10y: null }),
      point('2026-10-02', { spread_2y_10y: 40 }),
      point('2026-10-03', { spread_2y_10y: null }),
      point('2026-10-04', { spread_2y_10y: 65.25 }),
      point('2026-10-05', { spread_2y_10y: null }),
    ]
    expect(measureStats(points, 'spread_2y_10y')).toEqual({ last: 65.25, min: 40, max: 65.25, changeBp: 25.3 })
  })

  it('stats are empty without values, and change is undefined with one value', () => {
    expect(measureStats([], 'spread_2y_10y')).toEqual({ last: undefined, min: undefined, max: undefined, changeBp: undefined })
    const one = [point('2026-10-01', { spread_2y_10y: null }), point('2026-10-02', { spread_2y_10y: -3 })]
    expect(measureStats(one, 'spread_2y_10y')).toEqual({ last: -3, min: -3, max: -3, changeBp: undefined })
  })

  it('counts a spread inverted only when its own value is below zero', () => {
    const points = [
      point('2026-10-01', { spread_2y_10y: -5 }),
      point('2026-10-02', { spread_2y_10y: 0 }),
      point('2026-10-03', { spread_2y_10y: null }),
      point('2026-10-04', { spread_2y_10y: 12 }),
    ]
    expect(invertedDays(points, 'spread_2y_10y')).toEqual({ inverted: 1, total: 3 })
    expect(invertedHint(invertedDays(points, 'spread_2y_10y'))).toBe('Inverted on 1 of 3 days')
  })

  it('uses the 3M–10Y value, not the API inverted flag, for the 3M–10Y spread', () => {
    const points = [
      point('2026-10-01', { spread_3m_10y: -2, inverted: false }),
      point('2026-10-02', { spread_3m_10y: 4, inverted: true }),
    ]
    expect(invertedDays(points, 'spread_3m_10y')).toEqual({ inverted: 1, total: 2 })
  })

  it('reports no inverted days and an empty total when nothing has a value', () => {
    expect(invertedDays([], 'spread_2y_10y')).toEqual({ inverted: 0, total: 0 })
    expect(invertedDays([point('2026-10-01', { spread_2y_10y: null })], 'spread_2y_10y')).toEqual({ inverted: 0, total: 0 })
  })

  it('lists the flagged inputs of the measure only', () => {
    const p = point('2026-10-01', { quality: { status: 'warn', flagged: ['3M', '5Y'] } })
    expect(measureFlagged(p, 'spread_3m_10y')).toEqual(['3M'])
    expect(measureFlagged(p, 'spread_2y_10y')).toEqual([])
    expect(measureFlagged(p, 'curvature_2y_5y_10y')).toEqual(['5Y'])
  })
})
