import { cleanup, fireEvent, render, screen, waitFor, within } from '../test/render'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { localInputToUtc } from '../asOf'
import { formatUtc } from '../format'
import CurveChart from './CurveChart'
import CurveView from './CurveView'
import { fetchCurve, type CurveResult } from './fetchCurve'
import VersionHistory from '../versions/VersionHistory'

vi.mock('./CurveChart', () => ({
  default: vi.fn(() => null),
}))

vi.mock('./fetchCurve', () => ({
  fetchCurve: vi.fn(),
}))

vi.mock('../versions/VersionHistory', () => ({
  default: vi.fn(() => null),
}))

const mockedFetch = vi.mocked(fetchCurve)
const mockedHistory = vi.mocked(VersionHistory)
const mockedChart = vi.mocked(CurveChart)

function curveResult(validDate: string, values: (number | null)[]): CurveResult {
  const grid = ['3M', '1Y', '10Y', '15Y', '20Y']
  const months = [3, 12, 120, 180, 240]
  return {
    kind: 'ok',
    curve: {
      data: {
        curve_id: 'ecb-aaa-spot',
        valid_date: validDate,
        points: grid.map((maturity, i) => ({
          maturity,
          months: months[i],
          value: values[i],
          version_id: values[i] === null ? null : 1,
          origin: 'published' as const,
        })),
      },
      meta: { as_of: '2026-10-19T10:00:00Z', source_attribution: 'Source: ECB statistics' },
    },
  }
}

beforeEach(() => {
  mockedFetch.mockImplementation(async ({ validDate }) =>
    curveResult(validDate ?? '2026-10-16', [2.1, 2.4, 2.6, null, null]),
  )
})

afterEach(() => {
  cleanup()
  vi.clearAllMocks()
  window.history.replaceState(null, '', '/')
})

async function renderLoaded() {
  const view = render(<CurveView curveId="ecb-aaa-spot" />)
  await waitFor(() => expect(screen.getByLabelText(/Valid date/)).toHaveValue('2026-10-16'))
  return view
}

function addButton() {
  return screen.getByRole('button', { name: 'Add to overlay' })
}

function pickDate(date: string) {
  fireEvent.change(screen.getByLabelText(/Valid date/), { target: { value: date } })
}

function chartLabels(): string[] {
  const last = mockedChart.mock.lastCall
  return last ? last[0].curves.map((curve) => curve.label) : []
}

describe('CurveView', () => {
  it('shows the latest curve on open', async () => {
    render(<CurveView curveId="ecb-aaa-spot" />)

    expect(await screen.findByLabelText(/Valid date/)).toHaveValue('2026-10-16')
    expect(mockedFetch).toHaveBeenCalledWith({ curveId: 'ecb-aaa-spot', validDate: undefined, asOf: undefined })
  })

  it('has one h1, the page title', async () => {
    render(<CurveView curveId="ecb-aaa-spot" />)

    expect(await screen.findByLabelText(/Valid date/)).toHaveValue('2026-10-16')
    const headings = screen.getAllByRole('heading', { level: 1 })
    expect(headings).toHaveLength(1)
    expect(headings[0]).toHaveTextContent('ECB euro area AAA spot')
  })

  it('marks missing points', async () => {
    render(<CurveView curveId="ecb-aaa-spot" />)

    expect(await screen.findByText('No value for: 15Y, 20Y')).toBeInTheDocument()
  })

  it('refetches for a picked date', async () => {
    render(<CurveView curveId="ecb-aaa-spot" />)
    const input = await screen.findByLabelText(/Valid date/)

    fireEvent.change(input, { target: { value: '2026-10-01' } })

    expect(mockedFetch).toHaveBeenLastCalledWith({ curveId: 'ecb-aaa-spot', validDate: '2026-10-01', asOf: undefined })
  })

  it('shows the offline state', async () => {
    mockedFetch.mockResolvedValue({ kind: 'offline' })

    render(<CurveView curveId="ecb-aaa-spot" />)

    expect(await screen.findByRole('alert')).toHaveTextContent('Backend offline')
  })

  it('passes asOf to the API', async () => {
    render(<CurveView curveId="ecb-aaa-spot" asOf="2026-10-01T12:00:00Z" />)

    await waitFor(() =>
      expect(mockedFetch).toHaveBeenCalledWith({
        curveId: 'ecb-aaa-spot',
        validDate: undefined,
        asOf: '2026-10-01T12:00:00Z',
      }),
    )
  })

  it('shows no data known as of the chosen time', async () => {
    const asOf = localInputToUtc('2026-10-01T12:00:00')
    mockedFetch.mockImplementation(async (options) =>
      options.asOf
        ? { kind: 'not-found', detail: 'no curve as of then' }
        : curveResult('2026-10-16', [2.1, 2.4, 2.6, null, null]),
    )
    render(<CurveView curveId="ecb-aaa-spot" asOf={asOf} />)

    expect(await screen.findByText(`No data known as of ${formatUtc(asOf)}`)).toBeInTheDocument()
  })

  it('overlays a second date', async () => {
    await renderLoaded()
    fireEvent.click(addButton())

    pickDate('2026-10-01')
    fireEvent.click(addButton())

    expect(mockedFetch).toHaveBeenCalledWith({ curveId: 'ecb-aaa-spot', validDate: '2026-10-01', asOf: undefined })
    const overlays = screen.getByRole('list', { name: 'Overlaid valid dates' })
    expect(within(overlays).getAllByRole('listitem')).toHaveLength(2)
    await waitFor(() => expect(chartLabels()).toEqual(['2026-10-01', '2026-10-16']))
  })

  it('removes an overlaid date', async () => {
    await renderLoaded()
    fireEvent.click(addButton())
    pickDate('2026-10-01')
    fireEvent.click(addButton())

    fireEvent.click(screen.getByRole('button', { name: 'Remove 2026-10-16' }))

    expect(screen.queryByRole('button', { name: 'Remove 2026-10-16' })).not.toBeInTheDocument()
    await waitFor(() => expect(chartLabels()).toEqual(['2026-10-01']))
  })

  it('refetches overlays when asOf changes', async () => {
    const { rerender } = await renderLoaded()
    fireEvent.click(addButton())
    pickDate('2026-10-01')
    fireEvent.click(addButton())
    const asOf = localInputToUtc('2026-10-01T12:00:00')

    // The same Fragment wrapper as the initial render, so React updates the view instead of remounting it.
    rerender(
      <>
        <CurveView curveId="ecb-aaa-spot" asOf={asOf} />
      </>,
    )

    await waitFor(() =>
      expect(mockedFetch).toHaveBeenCalledWith({ curveId: 'ecb-aaa-spot', validDate: '2026-10-16', asOf }),
    )
    expect(mockedFetch).toHaveBeenCalledWith({ curveId: 'ecb-aaa-spot', validDate: '2026-10-01', asOf })
  })

  it('opens the history of a maturity', async () => {
    await renderLoaded()

    expect(screen.queryByRole('button', { name: 'History 15Y' })).not.toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'History 10Y' }))

    expect(mockedHistory.mock.lastCall?.[0]).toMatchObject({
      maturity: '10Y',
      validDate: '2026-10-16',
      asOf: undefined,
    })
  })

  it('caps the overlay at 5 curves', async () => {
    await renderLoaded()
    const dates = ['2026-10-16', '2026-10-01', '2026-09-30', '2026-09-29', '2026-09-28']
    for (const date of dates) {
      pickDate(date)
      fireEvent.click(addButton())
    }

    const overlays = screen.getByRole('list', { name: 'Overlaid valid dates' })
    expect(within(overlays).getAllByRole('listitem')).toHaveLength(5)
    pickDate('2026-09-27')
    expect(addButton()).toBeDisabled()
  })
})
