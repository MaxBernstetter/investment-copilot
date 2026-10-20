import { formatYield } from '../format'
import { cleanup, fireEvent, render, screen } from '../test/render'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { fetchSeries, type SeriesResult } from './fetchSeries'
import SeriesView from './SeriesView'

vi.mock('./SeriesChart', () => ({
  default: () => <div data-testid="series-chart" />,
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
      points: [
        { valid_date: '2026-10-01', value: 2.5, version_id: 1, origin: 'published' },
        { valid_date: '2026-10-16', value: 2.6, version_id: 3, origin: 'published' },
      ],
    },
    meta: { as_of: '2026-10-19T10:00:00Z', source_attribution: 'Source: ECB statistics' },
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
    render(<SeriesView curveId="ecb-aaa-spot" />)

    expect(await screen.findByLabelText('Maturity')).toHaveValue('10Y')
    expect(screen.getByLabelText('From')).toHaveValue('2025-10-19')
    expect(screen.getByLabelText('To')).toHaveValue('2026-10-19')
    expect(mockedFetch).toHaveBeenCalledWith({
      curveId: 'ecb-aaa-spot',
      maturity: '10Y',
      from: '2025-10-19',
      to: '2026-10-19',
      asOf: undefined,
    })
  })

  it('refetches when the maturity changes', async () => {
    render(<SeriesView curveId="ecb-aaa-spot" />)
    const select = await screen.findByLabelText('Maturity')

    fireEvent.change(select, { target: { value: '2Y' } })

    expect(mockedFetch).toHaveBeenLastCalledWith({
      curveId: 'ecb-aaa-spot',
      maturity: '2Y',
      from: '2025-10-19',
      to: '2026-10-19',
      asOf: undefined,
    })
  })

  it('passes asOf to the fetch', async () => {
    render(<SeriesView curveId="ecb-aaa-spot" asOf="2026-10-01T12:00:00Z" />)

    expect(await screen.findByLabelText('Maturity')).toHaveValue('10Y')
    expect(mockedFetch).toHaveBeenCalledWith(expect.objectContaining({ asOf: '2026-10-01T12:00:00Z' }))
  })

  it('shows stat cards from the loaded points', async () => {
    render(<SeriesView curveId="ecb-aaa-spot" />)

    expect(await screen.findByText('Last')).toBeInTheDocument()
    expect(screen.getByText('2.500 %')).toBeInTheDocument()
    expect(screen.getByText('Change over range')).toBeInTheDocument()
    expect(screen.getByText('+10.0 bp')).toBeInTheDocument()
  })

  it('shows a negative change over range', async () => {
    mockedFetch.mockResolvedValue({
      kind: 'ok',
      series: {
        data: {
          curve_id: 'ecb-aaa-spot',
          maturity: '10Y',
          points: [
            { valid_date: '2026-10-01', value: 3, version_id: 1, origin: 'published' },
            { valid_date: '2026-10-16', value: 2.5, version_id: 2, origin: 'published' },
          ],
        },
        meta: { as_of: '2026-10-19T10:00:00Z', source_attribution: 'Source: ECB statistics' },
      },
    })

    render(<SeriesView curveId="ecb-aaa-spot" />)

    expect(await screen.findByText('−50.0 bp')).toBeInTheDocument()
  })

  it('toggles between chart and table', async () => {
    render(<SeriesView curveId="ecb-aaa-spot" />)

    expect(await screen.findByTestId('series-chart')).toBeInTheDocument()
    fireEvent.click(screen.getByRole('radio', { name: 'Table' }))
    expect(screen.queryByTestId('series-chart')).not.toBeInTheDocument()
    expect(screen.getByRole('columnheader', { name: 'Valid date' })).toBeInTheDocument()
    expect(screen.getByRole('cell', { name: formatYield(2.6) })).toBeInTheDocument()
    fireEvent.click(screen.getByRole('radio', { name: 'Chart' }))
    expect(screen.getByTestId('series-chart')).toBeInTheDocument()
  })

  it('shows the offline alert', async () => {
    mockedFetch.mockResolvedValue({ kind: 'offline' })

    render(<SeriesView curveId="ecb-aaa-spot" />)

    expect(await screen.findByRole('alert')).toHaveTextContent('Backend offline')
  })
})
