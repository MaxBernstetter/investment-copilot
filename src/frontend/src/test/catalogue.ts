import type { CurveInfo } from '../curve/fetchCurves'

const GRID = [
  { maturity: '3M', months: 3 },
  { maturity: '6M', months: 6 },
  { maturity: '1Y', months: 12 },
  { maturity: '2Y', months: 24 },
  { maturity: '3Y', months: 36 },
  { maturity: '5Y', months: 60 },
  { maturity: '7Y', months: 84 },
  { maturity: '10Y', months: 120 },
  { maturity: '15Y', months: 180 },
  { maturity: '20Y', months: 240 },
  { maturity: '30Y', months: 360 },
]

const BASE: Omit<CurveInfo, 'id' | 'label' | 'sourceId' | 'simulated' | 'attribution'> = {
  area: 'Euro area',
  rateType: 'spot',
  compounding: 'continuous',
  unit: 'percent',
  sourceModel: null,
  maturities: GRID,
}

/** Catalogue fixtures in API order (by curve_id), as the access API returns them. */
export const AAA: CurveInfo = {
  ...BASE,
  id: 'ecb-aaa-spot',
  label: 'ECB euro area AAA spot',
  sourceId: 'ecb',
  simulated: false,
  attribution: 'Source: ECB statistics',
}

export const SIM: CurveInfo = {
  ...BASE,
  id: 'ecb-aaa-spot-sim',
  label: 'ECB euro area AAA spot (scenario data)',
  sourceId: 'scenario',
  simulated: true,
  attribution: 'Simulated scenario based on ECB statistics',
}

export const ALL: CurveInfo = {
  ...BASE,
  id: 'ecb-all-spot',
  label: 'ECB euro area all-issuer spot',
  sourceId: 'ecb',
  simulated: false,
  attribution: 'Source: ECB statistics',
}

export const PAR: CurveInfo = {
  id: 'ust-par',
  label: 'US Treasury par',
  sourceId: 'ust',
  area: 'United States',
  rateType: 'par',
  compounding: 'semi-annual',
  unit: 'percent',
  sourceModel: null,
  simulated: false,
  attribution: 'Source: U.S. Department of the Treasury',
  maturities: GRID,
}

export const CATALOGUE: CurveInfo[] = [AAA, SIM, ALL]
