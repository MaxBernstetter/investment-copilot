import { describe, expect, it } from 'vitest'
import { missingMaturities, overlayRows, overlaySeries, type CurvePoint } from './curveData'

const points: CurvePoint[] = [
  { maturity: '3M', months: 3, value: 2.1, version_id: 1, origin: 'published' },
  { maturity: '1Y', months: 12, value: null, version_id: null, origin: 'published' },
  { maturity: '10Y', months: 120, value: 2.6, version_id: 3, origin: 'published' },
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
})
