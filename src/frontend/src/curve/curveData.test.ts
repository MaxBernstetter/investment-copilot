import { describe, expect, it } from 'vitest'
import {
  flaggedMaturities,
  missingMaturities,
  overlayRows,
  overlaySeries,
  tenYearHint,
  yield10y,
  type CurvePoint,
} from './curveData'

const passed = { status: 'passed' as const, flags: [] }

const points: CurvePoint[] = [
  { maturity: '3M', months: 3, value: 2.1, version_id: 1, origin: 'published', quality: passed },
  { maturity: '1Y', months: 12, value: null, version_id: null, origin: 'published', quality: null },
  { maturity: '10Y', months: 120, value: 2.6, version_id: 3, origin: 'published', quality: passed },
]

describe('curveData', () => {
  it('lists missing maturities', () => {
    expect(missingMaturities(points)).toEqual(['1Y'])
    expect(missingMaturities([points[0]])).toEqual([])
  })

  it('overlay rows keep grid order and nulls as gaps', () => {
    expect(
      overlayRows([
        { label: '2026-10-16', points },
        { label: '2026-10-01', points: [points[0]] },
      ]),
    ).toEqual([
      { maturity: '3M', '2026-10-16': 2.1, '2026-10-01': 2.1 },
      { maturity: '1Y', '2026-10-16': null, '2026-10-01': null },
      { maturity: '10Y', '2026-10-16': 2.6, '2026-10-01': null },
    ])
  })

  it('reads 10Y yield', () => {
    expect(yield10y(points)).toBe(2.6)
    expect(yield10y([points[0]])).toBeUndefined()
  })

  it('hints the 10Y yield when missing or flagged', () => {
    const flagged = (status: 'info' | 'warn'): CurvePoint[] => [
      { ...points[2], quality: { status, flags: [] } },
    ]
    expect(tenYearHint([points[0]])).toBe('Not available')
    expect(tenYearHint(flagged('warn'))).toBe('Value flagged')
    expect(tenYearHint(flagged('info'))).toBe('Value flagged')
    expect(tenYearHint([points[2]])).toBeUndefined()
  })

  it('flaggedMaturities lists info and warn maturities in grid order', () => {
    const flag = { rule: 'range', severity: 'warn' as const, explanation: '', evidence: '' }
    const grid: CurvePoint[] = [
      { maturity: '3M', months: 3, value: 2.1, version_id: 1, origin: 'published', quality: passed },
      { maturity: '2Y', months: 24, value: 2.3, version_id: 1, origin: 'published', quality: { status: 'info', flags: [] } },
      { maturity: '5Y', months: 60, value: 2.5, version_id: 1, origin: 'published', quality: { status: 'unchecked', flags: [] } },
      { maturity: '10Y', months: 120, value: 26.4, version_id: 1, origin: 'published', quality: { status: 'warn', flags: [flag] } },
      { maturity: '15Y', months: 180, value: null, version_id: null, origin: 'published', quality: null },
    ]
    expect(flaggedMaturities(grid)).toEqual(['2Y', '10Y'])
  })

  it('one series per curve named by valid date', () => {
    expect(
      overlaySeries([
        { label: '2026-10-16', points },
        { label: '2026-10-01', points: [points[0]] },
      ]),
    ).toEqual([
      { name: '2026-10-16', color: 'blue.8' },
      { name: '2026-10-01', color: 'orange.8' },
    ])
  })

  it('tenYearHint is Not available for a missing 10Y', () => {
    expect(tenYearHint([{ ...points[2], value: null, quality: null }])).toBe('Not available')
    expect(tenYearHint([points[0]])).toBe('Not available')
  })

  it('tenYearHint is Value flagged for a warn or info 10Y', () => {
    const warn: CurvePoint = { ...points[2], quality: { status: 'warn', flags: [] } }
    const info: CurvePoint = { ...points[2], quality: { status: 'info', flags: [] } }
    expect(tenYearHint([warn])).toBe('Value flagged')
    expect(tenYearHint([info])).toBe('Value flagged')
  })

  it('tenYearHint is undefined for a passed 10Y', () => {
    expect(tenYearHint(points)).toBeUndefined()
  })
})
