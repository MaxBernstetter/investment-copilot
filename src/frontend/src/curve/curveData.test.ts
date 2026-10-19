import { describe, expect, it } from 'vitest'
import { chartSeries, missingMaturities, type CurvePoint } from './curveData'

const points: CurvePoint[] = [
  { maturity: '3M', months: 3, value: 2.1 },
  { maturity: '1Y', months: 12, value: null },
  { maturity: '10Y', months: 120, value: 2.6 },
]

describe('curveData', () => {
  it('keeps grid order and null gaps', () => {
    expect(chartSeries(points)).toEqual({ x: ['3M', '1Y', '10Y'], y: [2.1, null, 2.6] })
  })

  it('lists missing maturities', () => {
    expect(missingMaturities(points)).toEqual(['1Y'])
    expect(missingMaturities([points[0]])).toEqual([])
  })
})
