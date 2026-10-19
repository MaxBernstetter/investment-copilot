import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import CurveView from './CurveView'
import { fetchCurve, type CurveResult } from './fetchCurve'

vi.mock('./CurveChart', () => ({
  default: () => null,
}))

vi.mock('./fetchCurve', () => ({
  fetchCurve: vi.fn(),
}))

const mockedFetch = vi.mocked(fetchCurve)

function curveResult(validDate: string, values: (number | null)[]): CurveResult {
  const grid = ['3M', '1Y', '10Y', '15Y', '20Y']
  const months = [3, 12, 120, 180, 240]
  return {
    kind: 'ok',
    curve: {
      data: {
        curve_id: 'ecb-aaa-spot',
        valid_date: validDate,
        points: grid.map((maturity, i) => ({ maturity, months: months[i], value: values[i] })),
      },
      meta: { as_of: '2026-10-19T10:00:00Z' },
    },
  }
}

beforeEach(() => {
  mockedFetch.mockResolvedValue(curveResult('2026-10-16', [2.1, 2.4, 2.6, null, null]))
})

afterEach(() => {
  cleanup()
  vi.clearAllMocks()
})

describe('CurveView', () => {
  it('shows the latest curve on open', async () => {
    render(<CurveView />)

    expect(await screen.findByLabelText(/Valid date/)).toHaveValue('2026-10-16')
    expect(mockedFetch).toHaveBeenCalledWith({ validDate: undefined })
    expect(screen.getByRole('link', { name: 'ECB statistics' })).toHaveAttribute(
      'href',
      'https://data.ecb.europa.eu/',
    )
  })

  it('marks missing points', async () => {
    render(<CurveView />)

    expect(await screen.findByText('No value for: 15Y, 20Y')).toBeInTheDocument()
  })

  it('refetches for a picked date', async () => {
    render(<CurveView />)
    const input = await screen.findByLabelText(/Valid date/)

    fireEvent.change(input, { target: { value: '2026-10-01' } })

    expect(mockedFetch).toHaveBeenLastCalledWith({ validDate: '2026-10-01' })
  })

  it('shows the offline state', async () => {
    mockedFetch.mockResolvedValue({ kind: 'offline' })

    render(<CurveView />)

    expect(await screen.findByRole('alert')).toHaveTextContent('Backend offline')
  })
})
