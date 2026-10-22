import { describe, expect, it } from 'vitest'
import { CURVES, curveById, curveSelectData, readCurveId, resolveCurve } from './curves'
import { AAA, ALL, CATALOGUE, SIM } from '../test/catalogue'

describe('curves', () => {
  it('reads the curve from the URL', () => {
    expect(readCurveId('?curve=ecb-aaa-spot-sim')).toBe('ecb-aaa-spot-sim')
    expect(readCurveId('?as_of=2026-10-01T12:00:00Z')).toBe('ecb-aaa-spot')
  })

  it('falls back to the real curve for an unknown id', () => {
    expect(readCurveId('?curve=nope')).toBe('ecb-aaa-spot')
    expect(curveById('nope').id).toBe('ecb-aaa-spot')
    expect(curveById('nope').isSimulated).toBe(false)
  })

  it('marks only the -sim curve as simulated', () => {
    expect(CURVES.filter((curve) => curve.isSimulated).map((curve) => curve.id)).toEqual([
      'ecb-aaa-spot-sim',
    ])
    expect(CURVES.every((curve) => curve.isSimulated === curve.id.endsWith('-sim'))).toBe(true)
  })

  it('resolves an exact id, then the default, then the first published curve', () => {
    expect(resolveCurve(CATALOGUE, 'ecb-all-spot')).toBe(ALL)
    expect(resolveCurve(CATALOGUE, 'nope')).toBe(AAA)
    expect(resolveCurve([SIM, ALL], 'nope')).toBe(ALL)
    expect(resolveCurve([SIM], 'nope')).toBe(SIM)
    expect(resolveCurve([], 'ecb-aaa-spot')).toBeUndefined()
  })

  it('groups the select options, published first, dropping an empty group', () => {
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
    expect(curveSelectData([AAA])).toHaveLength(1)
  })
})
