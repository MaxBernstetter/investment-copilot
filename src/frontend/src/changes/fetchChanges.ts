import { api } from '../api/client'
import type { components } from '../api/schema'

export type ChangesResult =
  | { kind: 'ok'; changes: components['schemas']['CurveChangesResponse'] }
  | { kind: 'not-found'; detail: string }
  | { kind: 'invalid'; detail: string }
  | { kind: 'offline' }
  | { kind: 'error'; detail: string }

type FetchChangesOptions = {
  curveId: string
  from: string
  to: string
  since: string
  asOf?: string
}

export async function fetchChanges({
  curveId,
  from,
  to,
  since,
  asOf,
}: FetchChangesOptions): Promise<ChangesResult> {
  const query = {
    from,
    to,
    since,
    ...(asOf !== undefined ? { as_of: asOf } : {}),
  }
  const result = await api
    .GET('/v1/curves/{curve_id}/changes', {
      params: { path: { curve_id: curveId }, query },
    })
    .catch(() => undefined)
  if (result === undefined) return { kind: 'offline' }

  const { data, error, response } = result
  if (data) return { kind: 'ok', changes: data }

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
