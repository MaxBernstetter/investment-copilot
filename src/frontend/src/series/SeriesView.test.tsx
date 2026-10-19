import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { localInputToUtc } from '../asOf'
import { fetchSeries, type SeriesResult } from './fetchSeries'
import SeriesView from './SeriesView'

vi.mock('./SeriesChart', () => ({
  default: () => null,
}))

vi.mock('./fetchSeries', () => ({
  fetchSeries: vi.fn(),
}))

const mockedFetch = vi.mocked(fetchSeries)

const okResult: SeriesResult = {
  kind: 'ok',
  series: {
    data: {
      curve_id: 'ecb-aaa-spot',
      maturity: '10Y',
      points: [{ valid_date: '2026-10-16', value: 2.6 }],
    },
    meta: { as_of: '2026-10-19T10:00:00Z' },
  },
}

beforeEach(() => {
  vi.useFakeTimers({ toFake: ['Date'] })
  vi.setSystemTime(new Date('2026-10-19T12:00:00Z'))
  mockedFetch.mockResolvedValue(okResult)
})

afterEach(() => {
  cleanup()
  vi.clearAllMocks()
  vi.useRealTimers()
  window.history.replaceState(null, '', '/')
})

describe('SeriesView', () => {
  it('shows the 10Y series of the last year on open', async () => {
    render(<SeriesView />)

    expect(await screen.findByLabelText('Maturity')).toHaveValue('10Y')
    expect(screen.getByLabelText('From')).toHaveValue('2025-10-19')
    expect(screen.getByLabelText('To')).toHaveValue('2026-10-19')
    expect(mockedFetch).toHaveBeenCalledWith({
      maturity: '10Y',
      from: '2025-10-19',
      to: '2026-10-19',
      asOf: undefined,
    })
  })

  it('refetches when the maturity changes', async () => {
    render(<SeriesView />)
    const select = await screen.findByLabelText('Maturity')

    fireEvent.change(select, { target: { value: '2Y' } })

    expect(mockedFetch).toHaveBeenLastCalledWith({
      maturity: '2Y',
      from: '2025-10-19',
      to: '2026-10-19',
      asOf: undefined,
    })
  })

  it('reads as_of from the URL and writes it on change', async () => {
    window.history.replaceState(null, '', '/?as_of=2026-10-01T12:00:00Z')
    render(<SeriesView />)
    await screen.findByRole('status')

    expect(mockedFetch).toHaveBeenCalledWith(
      expect.objectContaining({ asOf: '2026-10-01T12:00:00Z' }),
    )

    const chosen = '2026-10-02T09:30:00'
    fireEvent.change(screen.getByLabelText(/Known as of/), { target: { value: chosen } })

    expect(new URLSearchParams(window.location.search).get('as_of')).toBe(
      localInputToUtc(chosen),
    )
  })

  it('shows the offline alert', async () => {
    mockedFetch.mockResolvedValue({ kind: 'offline' })

    render(<SeriesView />)

    expect(await screen.findByRole('alert')).toHaveTextContent('Backend offline')
  })
})
