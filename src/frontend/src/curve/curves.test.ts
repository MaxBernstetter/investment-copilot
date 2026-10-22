import { describe, expect, it } from 'vitest'
import { curveSelectData, readCurveId, resolveCurve } from './curves'
import { AAA, ALL, CATALOGUE, SIM } from '../test/catalogue'

describe('curves', () => {
  it('reads the curve id from the URL', () => {
    expect(readCurveId('?curve=ecb-aaa-spot-sim')).toBe('ecb-aaa-spot-sim')
    expect(readCurveId('?as_of=2026-10-01T12:00:00Z')).toBe('ecb-aaa-spot')
    expect(readCurveId('?curve=nope')).toBe('nope')
  })

  it('resolves an exact id', () => {
    expect(resolveCurve(CATALOGUE, 'ecb-all-spot')).toBe(ALL)
    expect(resolveCurve(CATALOGUE, 'ecb-aaa-spot-sim')).toBe(SIM)
  })

  it('falls back to the default curve for an unknown id', () => {
    expect(resolveCurve(CATALOGUE, 'nope')).toBe(AAA)
  })

  it('falls back to the first published curve without the default, never to a simulated one', () => {
    expect(resolveCurve([SIM, ALL], 'nope')).toBe(ALL)
  })

  it('falls back to the first curve when every curve is simulated', () => {
    expect(resolveCurve([SIM], 'nope')).toBe(SIM)
  })

  it('gives no curve for an empty catalogue', () => {
    expect(resolveCurve([], 'ecb-aaa-spot')).toBeUndefined()
  })

  it('groups the select options, published first, in catalogue order', () => {
    expect(curveSelectData(CATALOGUE)).toEqual([
      {
        group: 'Published',
        items: [
          { value: 'ecb-aaa-spot', label: 'ECB euro area AAA spot' },
          { value: 'ecb-all-spot', label: 'ECB euro area all-issuer spot' },
        ],
      },
      { group: 'Simulated', items: [{ value: 'ecb-aaa-spot-sim', label: 'ECB euro area AAA spot (scenario data)' }] },
    ])
  })

  it('drops an empty group', () => {
    expect(curveSelectData([AAA])).toEqual([
      { group: 'Published', items: [{ value: 'ecb-aaa-spot', label: 'ECB euro area AAA spot' }] },
    ])
  })
})
