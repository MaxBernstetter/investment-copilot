import { api } from '../api/client'
import type { components } from '../api/schema'
import { CURVE_ID } from '../curve/fetchCurve'

export type SeriesResult =
  | { kind: 'ok'; series: components['schemas']['SeriesObservationsResponse'] }
  | { kind: 'not-found'; detail: string }
  | { kind: 'invalid'; detail: string }
  | { kind: 'offline' }
  | { kind: 'error'; detail: string }

type FetchSeriesOptions = {
  maturity: string
  from: string
  to: string
  asOf?: string
}

export async function fetchSeries({
  maturity,
  from,
  to,
  asOf,
}: FetchSeriesOptions): Promise<SeriesResult> {
  const query = {
    from,
    to,
    ...(asOf !== undefined ? { as_of: asOf } : {}),
  }
  const result = await api
    .GET('/v1/curves/{curve_id}/maturities/{maturity}/observations', {
      params: { path: { curve_id: CURVE_ID, maturity }, query },
    })
    .catch(() => undefined)
  if (result === undefined) return { kind: 'offline' }

  const { data, error, response } = result
  if (data) return { kind: 'ok', series: data }

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
