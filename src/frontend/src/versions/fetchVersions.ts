import { api } from '../api/client'
import type { components } from '../api/schema'

export type VersionsResult =
  | { kind: 'ok'; versions: components['schemas']['ValueVersionsResponse'] }
  | { kind: 'not-found'; detail: string }
  | { kind: 'invalid'; detail: string }
  | { kind: 'offline' }
  | { kind: 'error'; detail: string }

type FetchVersionsOptions = {
  curveId: string
  maturity: string
  validDate: string
  asOf?: string
}

export async function fetchVersions({
  curveId,
  maturity,
  validDate,
  asOf,
}: FetchVersionsOptions): Promise<VersionsResult> {
  const query = asOf !== undefined ? { as_of: asOf } : {}
  const result = await api
    .GET('/v1/curves/{curve_id}/maturities/{maturity}/observations/{valid_date}/versions', {
      params: { path: { curve_id: curveId, maturity, valid_date: validDate }, query },
    })
    .catch(() => undefined)
  if (result === undefined) return { kind: 'offline' }

  const { data, error, response } = result
  if (data) return { kind: 'ok', versions: data }

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
