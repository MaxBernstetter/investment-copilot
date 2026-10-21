import { cleanup, fireEvent, render, screen, waitFor, within } from '../test/render'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { localInputToUtc } from '../asOf'
import { formatUtc } from '../format'
import CurveChart from './CurveChart'
import CurveView from './CurveView'
import { fetchCurve, type CurveResult } from './fetchCurve'
import { fetchVersions } from '../versions/fetchVersions'
import type { ValueQuality } from '../quality/qualityData'

vi.mock('./CurveChart', () => ({
  default: vi.fn(() => null),
}))

vi.mock('./fetchCurve', () => ({
  fetchCurve: vi.fn(),
}))

vi.mock('../versions/fetchVersions', () => ({
  fetchVersions: vi.fn(),
}))

const mockedFetch = vi.mocked(fetchCurve)
const mockedVersions = vi.mocked(fetchVersions)
const mockedChart = vi.mocked(CurveChart)

const passedQuality = { status: 'passed' as const, flags: [] }

/** qualities[i], when given, replaces the default quality of grid point i. */
function curveResult(
  validDate: string,
  values: (number | null)[],
  qualities?: (ValueQuality | null)[],
): CurveResult {
  const grid = ['3M', '1Y', '2Y', '10Y', '15Y', '20Y']
  const months = [3, 12, 24, 120, 180, 240]
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
          quality: qualities?.[i] !== undefined ? qualities[i] : values[i] === null ? null : passedQuality,
        })),
      },
      meta: { as_of: '2026-10-19T10:00:00Z', source_attribution: 'Source: ECB statistics' },
    },
  }
}

beforeEach(() => {
  mockedFetch.mockImplementation(async ({ validDate }) =>
    curveResult(validDate ?? '2026-10-16', [2.1, 2.4, 2.5, 2.6, null, null]),
  )
  mockedVersions.mockResolvedValue({
    kind: 'ok',
    versions: {
      data: {
        curve_id: 'ecb-aaa-spot',
        maturity: '10Y',
        valid_date: '2026-10-16',
        versions: [],
      },
      meta: { as_of: '2026-10-19T10:00:00Z', source_attribution: 'Source: ECB statistics' },
    },
  })
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

function expectStatValue(label: string, value: string | RegExp) {
  const stack = screen.getByText(label).parentElement
  expect(stack).not.toBeNull()
  expect(within(stack!).getByText(value)).toBeInTheDocument()
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
    expect(headings[0]).toHaveTextContent('Yield curve')
  })

  it('shows the real-curve subtitle', async () => {
    render(<CurveView curveId="ecb-aaa-spot" />)

    expect(await screen.findByLabelText(/Valid date/)).toHaveValue('2026-10-16')
    expect(
      screen.getByText('ECB euro area AAA government bonds, spot rates by maturity'),
    ).toBeInTheDocument()
  })

  it('shows the simulated-curve subtitle', async () => {
    render(<CurveView curveId="ecb-aaa-spot-sim" />)

    expect(await screen.findByLabelText(/Valid date/)).toHaveValue('2026-10-16')
    expect(screen.getByText('Simulated scenario based on ECB AAA spot')).toBeInTheDocument()
  })

  it('shows key figures with formatted yield and spread', async () => {
    await renderLoaded()

    expectStatValue('10Y yield', /2\.600/)
    expectStatValue('2Y–10Y spread', '+10.0 bp')
    expectStatValue('Curve date', '2026-10-16')
    expectStatValue('Knowledge', 'Live')
  })

  it('shows a negative spread when 10Y is below 2Y', async () => {
    mockedFetch.mockImplementation(async ({ validDate }) =>
      curveResult(validDate ?? '2026-10-16', [2.1, 2.4, 3.0, 2.6, null, null]),
    )
    await renderLoaded()

    expectStatValue('2Y–10Y spread', '−40.0 bp')
  })

  it('values table has a Quality column after Yield', async () => {
    await renderLoaded()

    const headers = screen.getAllByRole('columnheader').map((header) => header.textContent)
    expect(headers).toEqual(['Maturity', 'Yield (%)', 'Quality', ''])
  })

  it('shows flag badges in the 10Y row before History', async () => {
    const range = { rule: 'range', severity: 'warn' as const, explanation: 'Out of range.', evidence: '26.400 % on 2026-10-16' }
    mockedFetch.mockImplementation(async ({ validDate }) =>
      curveResult(validDate ?? '2026-10-16', [2.1, 2.4, 2.5, 26.4, null, null], [
        null,
        null,
        null,
        { status: 'warn', flags: [range] },
        null,
        null,
      ]),
    )
    await renderLoaded()

    const row = screen.getByRole('button', { name: 'History 10Y' }).closest('tr')
    expect(row).not.toBeNull()
    const names = within(row!).getAllByRole('button').map((button) => button.getAttribute('aria-label') ?? button.textContent)
    expect(names).toEqual(['Range · warn, 10Y', 'History 10Y'])
  })

  it('captions list flagged maturities under the chart', async () => {
    const range = { rule: 'range', severity: 'warn' as const, explanation: 'Out of range.', evidence: '26.400 % on 2026-10-16' }
    mockedFetch.mockImplementation(async ({ validDate }) =>
      curveResult(validDate ?? '2026-10-16', [2.1, 2.4, 2.5, 26.4, null, null], [
        null,
        null,
        null,
        { status: 'warn', flags: [range] },
        null,
        null,
      ]),
    )
    await renderLoaded()

    expect(screen.getByText('Flagged: 10Y')).toBeInTheDocument()
  })

  it('no flagged caption when all values pass', async () => {
    await renderLoaded()

    expect(screen.queryByText(/^Flagged:/)).toBeNull()
  })

  it('shows the unchecked note only when a value is unchecked', async () => {
    mockedFetch.mockImplementation(async ({ validDate }) =>
      curveResult(validDate ?? '2026-10-16', [2.1, 2.4, 2.5, 2.6, null, null], [
        { status: 'unchecked', flags: [] },
        null,
        null,
        null,
        null,
        null,
      ]),
    )
    await renderLoaded()

    expect(screen.getByText('Unchecked means the quality checks have not run on the value yet.')).toBeInTheDocument()
  })

  it('no unchecked note when all values are checked', async () => {
    await renderLoaded()

    expect(screen.queryByText('Unchecked means the quality checks have not run on the value yet.')).toBeNull()
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
        : curveResult('2026-10-16', [2.1, 2.4, 2.5, 2.6, null, null]),
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

    fireEvent.click(await screen.findByRole('button', { name: 'Remove 2026-10-16' }))

    await waitFor(() =>
      expect(screen.queryByRole('button', { name: 'Remove 2026-10-16' })).not.toBeInTheDocument(),
    )
    await waitFor(() => expect(chartLabels()).toEqual(['2026-10-01']))
  })

  it('refetches overlays when asOf changes', async () => {
    const { rerender } = await renderLoaded()
    fireEvent.click(addButton())
    pickDate('2026-10-01')
    fireEvent.click(addButton())
    const asOf = localInputToUtc('2026-10-01T12:00:00')

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

  it('opens and closes the history drawer', async () => {
    await renderLoaded()

    expect(screen.queryByRole('button', { name: 'History 15Y' })).not.toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'History 10Y' }))

    expect(screen.getByRole('heading', { name: 'History of 10Y on 2026-10-16' })).toBeInTheDocument()
    expect(mockedVersions).toHaveBeenCalledWith({
      curveId: 'ecb-aaa-spot',
      maturity: '10Y',
      validDate: '2026-10-16',
      asOf: undefined,
    })

    fireEvent.click(screen.getByRole('button', { name: 'Close' }))
    await waitFor(() =>
      expect(screen.queryByRole('heading', { name: 'History of 10Y on 2026-10-16' })).not.toBeInTheDocument(),
    )
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
