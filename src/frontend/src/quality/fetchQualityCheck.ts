import { api } from '../api/client'
import type { components } from '../api/schema'

export type QualityCheckResult =
  | { kind: 'ok'; check: components['schemas']['QualityCheckResponse'] }
  | { kind: 'disabled'; detail: string }
  | { kind: 'not-found'; detail: string }
  | { kind: 'invalid'; detail: string }
  | { kind: 'offline' }
  | { kind: 'error'; detail: string }

type FetchQualityCheckOptions = {
  curveId: string
  from: string
  to: string
}

/** Starts a quality check of the range now and waits for it; only deployments that opt in allow it. */
export async function fetchQualityCheck({
  curveId,
  from,
  to,
}: FetchQualityCheckOptions): Promise<QualityCheckResult> {
  const result = await api
    .POST('/v1/curves/{curve_id}/quality/checks', {
      params: { path: { curve_id: curveId } },
      body: { valid_from: from, valid_to: to },
    })
    .catch(() => undefined)
  if (result === undefined) return { kind: 'offline' }

  const { data, error, response } = result
  if (data) return { kind: 'ok', check: data }

  const detail = error?.detail ?? 'Unexpected response from the API.'
  switch (response.status) {
    case 403:
      return { kind: 'disabled', detail }
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
