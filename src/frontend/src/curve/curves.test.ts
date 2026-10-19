import { describe, expect, it } from 'vitest'
import { CURVES, curveById, readCurveId } from './curves'

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
})
