import { api } from '../api/client'
import type { components } from '../api/schema'

type CurveDefinition = components['schemas']['CurveDefinition']

/** One curve of the catalogue, with its names in camelCase. */
export type CurveInfo = {
  id: string
  label: string
  sourceId: string
  area: string
  rateType: CurveDefinition['rate_type']
  compounding: CurveDefinition['compounding']
  unit: string
  sourceModel: string | null
  simulated: boolean
  attribution: string
  maturities: { maturity: string; months: number }[]
}

export type CurvesResult = { kind: 'ok'; curves: CurveInfo[] } | { kind: 'error' }

export function toCurveInfo(definition: CurveDefinition): CurveInfo {
  return {
    id: definition.curve_id,
    label: definition.label,
    sourceId: definition.source_id,
    area: definition.area,
    rateType: definition.rate_type,
    compounding: definition.compounding,
    unit: definition.unit,
    sourceModel: definition.source_model,
    simulated: definition.simulated,
    attribution: definition.attribution,
    maturities: definition.maturities,
  }
}

/** The curve catalogue from `GET /v1/curves`; any failure (network, 5xx) is an error result. */
export async function fetchCurves(): Promise<CurvesResult> {
  const result = await api.GET('/v1/curves').catch(() => undefined)
  const data = result?.data
  if (data === undefined) return { kind: 'error' }
  return { kind: 'ok', curves: data.data.map(toCurveInfo) }
}
