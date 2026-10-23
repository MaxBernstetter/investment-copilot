import { describe, expect, it } from 'vitest'
import { listWithOr, measureHint, measureValue, type MeasurePoint } from './measuresData'

const point = (overrides: Partial<MeasurePoint> = {}): MeasurePoint => ({
  valid_date: '2026-10-16',
  spread_2y_10y: 52.1,
  spread_3m_10y: 77.1,
  curvature_2y_5y_10y: -12.1,
  inverted: false,
  inputs: [],
  missing: [],
  quality: { status: 'passed', flagged: [] },
  ...overrides,
})

describe('measuresData', () => {
  it('listWithOr joins with commas and a final or', () => {
    expect(listWithOr(['5Y'])).toBe('5Y')
    expect(listWithOr(['2Y', '10Y'])).toBe('2Y or 10Y')
    expect(listWithOr(['3M', '2Y', '10Y'])).toBe('3M, 2Y or 10Y')
  })

  it('measureValue formats bp with a true minus and shows a dash for null', () => {
    expect(measureValue(point({ spread_2y_10y: 52.1 }), 'spread_2y_10y')).toBe('+52.1 bp')
    expect(measureValue(point(), 'curvature_2y_5y_10y')).toBe('\u221212.1 bp')
    expect(measureValue(point({ spread_3m_10y: null }), 'spread_3m_10y')).toBe('–')
    expect(measureValue(undefined, 'spread_3m_10y')).toBe('–')
  })

  it('hint is Not available without a point', () => {
    expect(measureHint(undefined, 'spread_2y_10y')).toBe('Not available')
  })

  it('hint names the missing 5Y for the curvature', () => {
    const curvature = point({ curvature_2y_5y_10y: null, missing: ['5Y'] })
    expect(measureHint(curvature, 'curvature_2y_5y_10y')).toBe('No 5Y value')
  })

  it('hint names only the missing inputs of the measure', () => {
    const missing = ['3M', '2Y', '10Y']
    expect(measureHint(point({ spread_2y_10y: null, missing }), 'spread_2y_10y')).toBe('No 2Y or 10Y value')
    expect(measureHint(point({ spread_3m_10y: null, missing }), 'spread_3m_10y')).toBe('No 3M or 10Y value')
  })

  it('hint is Not available for null with nothing missing', () => {
    expect(measureHint(point({ spread_2y_10y: null }), 'spread_2y_10y')).toBe('Not available')
  })

  it('hint names one flagged input for every measure', () => {
    const flagged = point({ quality: { status: 'warn', flagged: ['10Y'] } })
    expect(measureHint(flagged, 'spread_2y_10y')).toBe('Input flagged: 10Y')
    expect(measureHint(flagged, 'spread_3m_10y')).toBe('Input flagged: 10Y')
    expect(measureHint(flagged, 'curvature_2y_5y_10y')).toBe('Input flagged: 10Y')
  })

  it('hint names several flagged inputs', () => {
    const flagged = point({ quality: { status: 'warn', flagged: ['2Y', '10Y'] } })
    expect(measureHint(flagged, 'spread_2y_10y')).toBe('Inputs flagged: 2Y, 10Y')
  })

  it('hint ignores flags on inputs the measure does not use', () => {
    const flagged = point({ quality: { status: 'info', flagged: ['3M'] } })
    expect(measureHint(flagged, 'curvature_2y_5y_10y')).toBeUndefined()
  })

  it('has no hint for a present, unflagged value', () => {
    expect(measureHint(point(), 'spread_2y_10y')).toBeUndefined()
  })
})
