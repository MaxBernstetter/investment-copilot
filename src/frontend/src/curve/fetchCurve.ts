import { api } from '../api/client'
import type { components } from '../api/schema'

export const CURVE_ID = 'ecb-aaa-spot'

export type CurveResult =
  | { kind: 'ok'; curve: components['schemas']['CurveObservationsResponse'] }
  | { kind: 'not-found'; detail: string }
  | { kind: 'invalid'; detail: string }
  | { kind: 'offline' }
  | { kind: 'error'; detail: string }

type FetchCurveOptions = {
  validDate?: string
  asOf?: string
}

export async function fetchCurve({ validDate, asOf }: FetchCurveOptions = {}): Promise<CurveResult> {
  const query = {
    ...(validDate !== undefined ? { valid_date: validDate } : {}),
    ...(asOf !== undefined ? { as_of: asOf } : {}),
  }
  const result = await api
    .GET('/v1/curves/{curve_id}/observations', {
      params: { path: { curve_id: CURVE_ID }, query },
    })
    .catch(() => undefined)
  if (result === undefined) return { kind: 'offline' }

  const { data, error, response } = result
  if (data) return { kind: 'ok', curve: data }

  const detail = error?.detail ?? 'Unexpected response from the API.'
  switch (response.status) {
    case 503:
      return { kind: 'offline' }
    case 404:
      return { kind: 'not-found', detail }
    case 422:
      return { kind: 'invalid', detail }
    default:
      return { kind: 'error', detail }
  }
}
