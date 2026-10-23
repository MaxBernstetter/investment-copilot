import { beforeEach, describe, expect, it, vi } from 'vitest'
import { api } from '../api/client'
import { fetchMeasures } from './fetchMeasures'

vi.mock('../api/client', () => ({ api: { GET: vi.fn() } }))

const mockedGet = vi.mocked(api.GET)

const body = {
  data: { curve_id: 'ecb-aaa-spot', valid_from: '2026-10-16', valid_to: '2026-10-16', points: [] },
  meta: { as_of: '2026-10-19T10:00:00Z', method_version: '1', source_attribution: 'Source: ECB statistics' },
}

const failure = (status: number, detail: string) => ({
  data: undefined,
  error: { detail },
  response: new Response(null, { status }),
})

describe('fetchMeasures', () => {
  beforeEach(() => {
    mockedGet.mockReset()
  })

  it('requests the measures of one date at the given as_of', async () => {
    mockedGet.mockResolvedValue({ data: body, error: undefined, response: new Response(null, { status: 200 }) } as never)

    const result = await fetchMeasures({ curveId: 'ecb-aaa-spot', from: '2026-10-16', to: '2026-10-16', asOf: '2026-10-19T10:00:00Z' })

    expect(mockedGet).toHaveBeenCalledWith('/v1/curves/{curve_id}/measures', {
      params: {
        path: { curve_id: 'ecb-aaa-spot' },
        query: { from: '2026-10-16', to: '2026-10-16', as_of: '2026-10-19T10:00:00Z' },
      },
    })
    expect(result).toEqual({ kind: 'ok', measures: body })
  })

  it('omits as_of when no as_of is given', async () => {
    mockedGet.mockResolvedValue({ data: body, error: undefined, response: new Response(null, { status: 200 }) } as never)

    await fetchMeasures({ curveId: 'ecb-aaa-spot', from: '2026-10-16', to: '2026-10-16' })

    expect(mockedGet.mock.calls[0][1]).toEqual({
      params: { path: { curve_id: 'ecb-aaa-spot' }, query: { from: '2026-10-16', to: '2026-10-16' } },
    })
  })

  it('maps 503 to offline', async () => {
    mockedGet.mockResolvedValue(failure(503, 'unreachable') as never)

    expect(await fetchMeasures({ curveId: 'c', from: '2026-10-16', to: '2026-10-16' })).toEqual({ kind: 'offline' })
  })

  it('maps a rejected request to offline', async () => {
    mockedGet.mockRejectedValue(new TypeError('Failed to fetch'))

    expect(await fetchMeasures({ curveId: 'c', from: '2026-10-16', to: '2026-10-16' })).toEqual({ kind: 'offline' })
  })

  it('maps 404 to not-found and 422 to invalid with the detail', async () => {
    mockedGet.mockResolvedValueOnce(failure(404, 'No curve') as never)
    expect(await fetchMeasures({ curveId: 'c', from: '2026-10-16', to: '2026-10-16' })).toEqual({
      kind: 'not-found',
      detail: 'No curve',
    })

    mockedGet.mockResolvedValueOnce(failure(422, 'Bad date') as never)
    expect(await fetchMeasures({ curveId: 'c', from: '2026-10-16', to: '2026-10-16' })).toEqual({
      kind: 'invalid',
      detail: 'Bad date',
    })
  })

  it('maps other statuses to error', async () => {
    mockedGet.mockResolvedValue(failure(500, 'Boom') as never)

    expect(await fetchMeasures({ curveId: 'c', from: '2026-10-16', to: '2026-10-16' })).toEqual({
      kind: 'error',
      detail: 'Boom',
    })
  })
})
