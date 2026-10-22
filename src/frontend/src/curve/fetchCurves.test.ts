import { describe, expect, it } from 'vitest'
import type { components } from '../api/schema'
import { toCurveInfo } from './fetchCurves'

describe('fetchCurves', () => {
  it('maps a catalogue entry to CurveInfo', () => {
    const definition: components['schemas']['CurveDefinition'] = {
      curve_id: 'ecb-aaa-spot-sim',
      label: 'ECB euro area AAA spot (scenario data)',
      source_id: 'scenario',
      area: 'Euro area',
      rate_type: 'spot',
      compounding: 'continuous',
      unit: 'percent',
      source_model: 'nelson-siegel',
      simulated: true,
      attribution: 'Simulated scenario based on ECB statistics',
      maturities: [{ maturity: '3M', months: 3 }],
    }

    expect(toCurveInfo(definition)).toEqual({
      id: 'ecb-aaa-spot-sim',
      label: 'ECB euro area AAA spot (scenario data)',
      sourceId: 'scenario',
      area: 'Euro area',
      rateType: 'spot',
      compounding: 'continuous',
      unit: 'percent',
      sourceModel: 'nelson-siegel',
      simulated: true,
      attribution: 'Simulated scenario based on ECB statistics',
      maturities: [{ maturity: '3M', months: 3 }],
    })
  })
})
