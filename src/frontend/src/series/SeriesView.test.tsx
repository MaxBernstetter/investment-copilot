import { formatYield } from '../format'
import type { ValueQuality } from '../quality/qualityData'
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
        {
          valid_date: '2026-10-01',
          value: 2.5,
          version_id: 1,
          origin: 'published',
          quality: { status: 'passed', flags: [] },
        },
        {
          valid_date: '2026-10-16',
          value: 2.6,
          version_id: 3,
          origin: 'published',
          quality: { status: 'passed', flags: [] },
        },
      ],
    },
    meta: { as_of: '2026-10-19T10:00:00Z', source_attribution: 'Source: ECB statistics' },
  },
}

const rangeFlag = {
  rule: 'range',
  severity: 'warn' as const,
  explanation: 'Outside the plausible range of \u22122.00\u202f% to 8.00\u202f%.',
  evidence: '26.400\u202f% on 2026-10-16',
}

/** The OK result with one quality per point, in point order. */
function withQualities(qualities: ValueQuality[]): SeriesResult {
  if (okResult.kind !== 'ok') throw new Error('expected an ok result')
  const points = okResult.series.data.points.map((point, index) => ({ ...point, quality: qualities[index] }))
  return { kind: 'ok', series: { ...okResult.series, data: { ...okResult.series.data, points } } }
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

  it('states the unit in the chart card title', async () => {
    render(<SeriesView curveId="ecb-aaa-spot" />)

    expect(await screen.findByRole('heading', { name: '10Y yield (%)' })).toBeInTheDocument()
  })

  it('puts the chart in the padded card body, not a card section', async () => {
    render(<SeriesView curveId="ecb-aaa-spot" />)

    expect(await screen.findByRole('heading', { name: '10Y yield (%)' })).toBeInTheDocument()
    expect(document.querySelector('.mantine-Card-section')).toBeNull()
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
            {
              valid_date: '2026-10-01',
              value: 3,
              version_id: 1,
              origin: 'published',
              quality: { status: 'passed', flags: [] },
            },
            {
              valid_date: '2026-10-16',
              value: 2.5,
              version_id: 2,
              origin: 'published',
              quality: { status: 'passed', flags: [] },
            },
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

  it('chart caption counts flagged values', async () => {
    mockedFetch.mockResolvedValue(
      withQualities([
        { status: 'warn', flags: [rangeFlag] },
        { status: 'passed', flags: [] },
      ]),
    )
    const { unmount } = render(<SeriesView curveId="ecb-aaa-spot" />)
    expect(await screen.findByText('Flagged: 1 value. Choose Table to see why.')).toBeInTheDocument()
    unmount()

    mockedFetch.mockResolvedValue(
      withQualities([
        { status: 'warn', flags: [rangeFlag] },
        { status: 'info', flags: [] },
      ]),
    )
    render(<SeriesView curveId="ecb-aaa-spot" />)
    expect(await screen.findByText('Flagged: 2 values. Choose Table to see why.')).toBeInTheDocument()
  })

  it('no caption when nothing is flagged or the table shows', async () => {
    mockedFetch.mockResolvedValue(
      withQualities([
        { status: 'passed', flags: [] },
        { status: 'passed', flags: [] },
      ]),
    )
    const { unmount } = render(<SeriesView curveId="ecb-aaa-spot" />)
    expect(await screen.findByTestId('series-chart')).toBeInTheDocument()
    expect(screen.queryByText(/^Flagged:/)).not.toBeInTheDocument()
    unmount()

    mockedFetch.mockResolvedValue(
      withQualities([
        { status: 'warn', flags: [rangeFlag] },
        { status: 'passed', flags: [] },
      ]),
    )
    render(<SeriesView curveId="ecb-aaa-spot" />)
    expect(await screen.findByText('Flagged: 1 value. Choose Table to see why.')).toBeInTheDocument()
    fireEvent.click(screen.getByRole('radio', { name: 'Table' }))
    expect(screen.queryByText(/^Flagged:/)).not.toBeInTheDocument()
  })

  it('table shows a Quality column with flag badges', async () => {
    mockedFetch.mockResolvedValue(
      withQualities([
        { status: 'passed', flags: [] },
        { status: 'warn', flags: [rangeFlag] },
      ]),
    )
    render(<SeriesView curveId="ecb-aaa-spot" />)

    fireEvent.click(await screen.findByRole('radio', { name: 'Table' }))

    const headers = screen.getAllByRole('columnheader').map((header) => header.textContent)
    expect(headers).toEqual(['Valid date', 'Yield (%)', 'Quality'])
    expect(screen.getByRole('button', { name: 'Range · warn, 10Y' })).toBeInTheDocument()
  })

  it('table shows the unchecked note when a value is unchecked', async () => {
    mockedFetch.mockResolvedValue(
      withQualities([
        { status: 'unchecked', flags: [] },
        { status: 'passed', flags: [] },
      ]),
    )
    render(<SeriesView curveId="ecb-aaa-spot" />)

    fireEvent.click(await screen.findByRole('radio', { name: 'Table' }))
    expect(screen.getByText(/Unchecked means the quality checks have not run on the value yet\./)).toBeInTheDocument()
  })

  it('table has no unchecked note when all values are passed', async () => {
    render(<SeriesView curveId="ecb-aaa-spot" />)

    fireEvent.click(await screen.findByRole('radio', { name: 'Table' }))
    expect(screen.queryByText(/Unchecked means/)).not.toBeInTheDocument()
  })
})
