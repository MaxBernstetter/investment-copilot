import { describe, expect, it } from 'vitest'
import { CHART_COLORS } from '../theme'
import { AAA, ALL, PAR } from '../test/catalogue'
import type { CurveInfo } from './fetchCurves'
import {
  comparabilityIssue,
  distinctCurves,
  entryKey,
  flaggedMaturities,
  missingMaturities,
  monthsLabel,
  nextSlot,
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

  it('overlay rows are the sorted union of tenors, with nulls as gaps', () => {
    const short: CurvePoint = { maturity: '1.5M', months: 1.5, value: 2.0, version_id: 1, origin: 'published', quality: passed }
    const rows = overlayRows([
      { key: 'a', label: '2026-10-16', points: [...points, short], slot: 0 },
      { key: 'b', label: '2026-10-01', points: [points[0]], slot: 1 },
    ])
    expect(rows).toEqual([
      { months: 1.5, a: 2.0, b: null },
      { months: 3, a: 2.1, b: 2.1 },
      { months: 12, a: null, b: null },
      { months: 120, a: 2.6, b: null },
    ])
  })

  it('overlay rows keep one row per tenor across curves', () => {
    expect(overlayRows([{ key: 'a', label: 'x', points, slot: 0 }])).toEqual([
      { months: 3, a: 2.1 },
      { months: 12, a: null },
      { months: 120, a: 2.6 },
    ])
  })

  it('monthsLabel labels whole months, years and decimal months', () => {
    expect(monthsLabel(1.5)).toBe('1.5M')
    expect(monthsLabel(6)).toBe('6M')
    expect(monthsLabel(12)).toBe('1Y')
    expect(monthsLabel(18)).toBe('18M')
    expect(monthsLabel(24)).toBe('2Y')
    expect(monthsLabel(360)).toBe('30Y')
  })

  it('entryKey joins the curve id and valid date', () => {
    expect(entryKey({ curveId: 'ecb-aaa-spot', validDate: '2026-10-16' })).toBe('ecb-aaa-spot|2026-10-16')
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

  it('one series per curve, named by key and labelled by valid date', () => {
    expect(
      overlaySeries([
        { key: 'a|2026-10-16', label: '2026-10-16', points, slot: 0 },
        { key: 'a|2026-10-01', label: '2026-10-01', points: [points[0]], slot: 1 },
      ]),
    ).toEqual([
      { name: 'a|2026-10-16', label: '2026-10-16', color: 'blue.8' },
      { name: 'a|2026-10-01', label: '2026-10-01', color: 'orange.8' },
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

describe('colour slots', () => {
  it('nextSlot is the lowest free slot', () => {
    expect(nextSlot([])).toBe(0)
    expect(nextSlot([0])).toBe(1)
    expect(nextSlot([0, 1, 3])).toBe(2)
  })

  it('an overlay keeps its colour when a middle one is removed', () => {
    let slots = [0]
    slots = [...slots, nextSlot(slots)] // add A: 1
    slots = [...slots, nextSlot(slots)] // add B: 2
    slots = [...slots, nextSlot(slots)] // add C: 3
    slots = slots.filter((slot) => slot !== 2) // remove B
    expect(slots).toEqual([0, 1, 3])
  })

  it('a new overlay reuses the lowest free slot', () => {
    expect(nextSlot([0, 1, 3])).toBe(2)
  })

  it('the cap of five overlays gives six slots in total', () => {
    let slots = [0]
    for (let i = 0; i < 5; i++) slots = [...slots, nextSlot(slots)]
    expect(slots).toEqual([0, 1, 2, 3, 4, 5])
  })

  it('overlaySeries colours by slot, not by position', () => {
    const series = overlaySeries([
      { key: 'a', label: 'x', points, slot: 0 },
      { key: 'b', label: 'y', points, slot: 3 },
    ])
    expect(series.map((s) => s.color)).toEqual([CHART_COLORS[0], CHART_COLORS[3]])
  })
})

describe('comparabilityIssue', () => {
  const semiAnnualSpot: CurveInfo = { ...AAA, id: 'semi', compounding: 'semi-annual' }

  it('is undefined when the curves share rate type and compounding', () => {
    expect(comparabilityIssue([AAA, ALL])).toBeUndefined()
    expect(comparabilityIssue([AAA])).toBeUndefined()
    expect(comparabilityIssue([])).toBeUndefined()
  })

  it('is rate-type when spot and par are mixed with the same compounding', () => {
    expect(comparabilityIssue([AAA, { ...PAR, compounding: 'continuous' }])).toBe('rate-type')
  })

  it('is compounding when continuous and semi-annual are mixed with the same rate type', () => {
    expect(comparabilityIssue([AAA, semiAnnualSpot])).toBe('compounding')
  })

  it('is both when rate type and compounding differ', () => {
    expect(comparabilityIssue([AAA, PAR])).toBe('both')
  })
})

describe('distinctCurves', () => {
  const catalogue = [AAA, ALL, PAR]

  it('returns each catalogue curve once, in order of first appearance', () => {
    const entries = [
      { curveId: 'ust-par', validDate: '2026-10-16' },
      { curveId: 'ecb-aaa-spot', validDate: '2026-10-15' },
      { curveId: 'ust-par', validDate: '2026-10-14' },
      { curveId: 'ecb-aaa-spot', validDate: '2026-10-13' },
    ]
    expect(distinctCurves(entries, catalogue).map((curve) => curve.id)).toEqual(['ust-par', 'ecb-aaa-spot'])
  })

  it('skips an entry whose curve is not in the catalogue', () => {
    const entries = [
      { curveId: 'gone', validDate: '2026-10-15' },
      { curveId: 'ecb-all-spot', validDate: '2026-10-15' },
    ]
    expect(distinctCurves(entries, catalogue).map((curve) => curve.id)).toEqual(['ecb-all-spot'])
  })
})
