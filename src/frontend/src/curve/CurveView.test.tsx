import { cleanup, fireEvent, render, screen, waitFor, within } from '../test/render'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { localInputToUtc } from '../asOf'
import { formatUtc } from '../format'
import CurveChart from './CurveChart'
import CurveView from './CurveView'
import { fetchCurve, type CurveResult } from './fetchCurve'
import { fetchVersions } from '../versions/fetchVersions'
import type { ValueQuality } from '../quality/qualityData'
import { AAA, ALL, CATALOGUE, PAR, SIM } from '../test/catalogue'
import { fetchMeasures, type MeasuresResult } from './fetchMeasures'
import type { MeasurePoint } from './measuresData'
import type { CurveInfo } from './fetchCurves'
import { useOverlay } from './useOverlay'

vi.mock('./CurveChart', () => ({
  default: vi.fn(() => null),
}))

vi.mock('./fetchCurve', () => ({
  fetchCurve: vi.fn(),
}))

vi.mock('../versions/fetchVersions', () => ({
  fetchVersions: vi.fn(),
}))

vi.mock('./fetchMeasures', () => ({
  fetchMeasures: vi.fn(),
}))

const mockedFetch = vi.mocked(fetchCurve)
const mockedVersions = vi.mocked(fetchVersions)
const mockedMeasures = vi.mocked(fetchMeasures)
const mockedChart = vi.mocked(CurveChart)

/** App's wiring: the overlay is owned above the curve view and keeps its entries across curve switches. */
function Host({ curve, asOf, catalogue = CATALOGUE }: { curve: CurveInfo; asOf?: string; catalogue?: CurveInfo[] }) {
  const overlay = useOverlay(catalogue)
  return <CurveView key={curve.id} curve={curve} catalogue={catalogue} overlay={overlay} asOf={asOf} />
}

const passedQuality = { status: 'passed' as const, flags: [] }

/** A measures answer for one valid date; overrides change the point of that date. */
function measuresResult(validDate: string, overrides: Partial<MeasurePoint> = {}): MeasuresResult {
  return {
    kind: 'ok',
    measures: {
      data: {
        curve_id: 'ecb-aaa-spot',
        valid_from: validDate,
        valid_to: validDate,
        points: [
          {
            valid_date: validDate,
            spread_2y_10y: 52.1,
            spread_3m_10y: 77.1,
            curvature_2y_5y_10y: -12.1,
            inverted: false,
            inputs: [],
            missing: [],
            quality: { status: 'passed', flagged: [] },
            ...overrides,
          },
        ],
      },
      meta: {
        as_of: '2026-10-19T10:00:00Z',
        method_version: '1',
        source_attribution: 'Source: ECB statistics',
      },
    },
  }
}

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
  mockedMeasures.mockImplementation(async ({ from }) => measuresResult(from))
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
  const view = render(<Host curve={AAA} />)
  await waitFor(() => expect(screen.getByLabelText(/Valid date/)).toHaveValue('2026-10-16'))
  return view
}

/** Waits until the key figures have their measures (the grid is no longer aria-busy). */
async function waitForMeasures() {
  await waitFor(() =>
    expect(screen.getByText('10Y yield').closest('.mantine-SimpleGrid-root')).not.toHaveAttribute('aria-busy'),
  )
}

const ASOF = '2026-10-19T10:00:00Z'

function addButton() {
  return screen.getByRole('button', { name: 'Add to overlay' })
}

function pickDate(date: string) {
  fireEvent.change(screen.getByLabelText(/Valid date/), { target: { value: date } })
}

/** The polite live region that announces overlay changes. */
function announcement(): HTMLElement {
  const region = document.querySelector<HTMLElement>('[aria-live="polite"]')
  expect(region).not.toBeNull()
  return region as HTMLElement
}

function chartLabels(): string[] {
  const last = mockedChart.mock.lastCall
  return last ? last[0].curves.map((curve) => curve.label) : []
}

function statCard(label: string): HTMLElement {
  const card = screen.getByText(label).closest('.mantine-Card-root')
  expect(card).not.toBeNull()
  return card as HTMLElement
}

function expectStatValue(label: string, value: string | RegExp) {
  expect(within(statCard(label)).getByText(value)).toBeInTheDocument()
}

function expectStatHint(label: string, hint: string) {
  expect(within(statCard(label)).getByText(hint)).toBeInTheDocument()
}

describe('CurveView', () => {
  it('shows the latest curve on open', async () => {
    render(<Host curve={AAA} />)

    expect(await screen.findByLabelText(/Valid date/)).toHaveValue('2026-10-16')
    expect(mockedFetch).toHaveBeenCalledWith({ curveId: 'ecb-aaa-spot', validDate: undefined, asOf: undefined })
  })

  it('has one h1, the page title', async () => {
    render(<Host curve={AAA} />)

    expect(await screen.findByLabelText(/Valid date/)).toHaveValue('2026-10-16')
    const headings = screen.getAllByRole('heading', { level: 1 })
    expect(headings).toHaveLength(1)
    expect(headings[0]).toHaveTextContent('Yield curve')
  })

  it('puts the chart in the padded card body, not a card section', async () => {
    await renderLoaded()

    expect(document.querySelector('.mantine-Card-section')).toBeNull()
    expect(screen.getByRole('heading', { name: 'Spot curve (%)' })).toBeInTheDocument()
  })

  it('shows the label and convention in the subtitle', async () => {
    render(<Host curve={AAA} />)
    expect(await screen.findByLabelText(/Valid date/)).toHaveValue('2026-10-16')
    expect(screen.getByText('ECB euro area AAA spot · spot rates, continuous compounding')).toBeInTheDocument()
  })

  it('shows the simulated label in the subtitle', async () => {
    render(<Host curve={SIM} />)
    expect(await screen.findByLabelText(/Valid date/)).toHaveValue('2026-10-16')
    expect(
      screen.getByText('ECB euro area AAA spot (scenario data) · spot rates, continuous compounding'),
    ).toBeInTheDocument()
  })

  it('names the chart card after the rate type', async () => {
    render(<Host curve={PAR} />)
    expect(await screen.findByLabelText(/Valid date/)).toHaveValue('2026-10-16')
    expect(screen.getByRole('heading', { name: 'Par curve (%)' })).toBeInTheDocument()
    expect(screen.getByText('US Treasury par · par rates, semi-annual compounding')).toBeInTheDocument()
  })

  it('explains the valid date with the publisher', async () => {
    await renderLoaded()
    await userEvent.setup().hover(screen.getByRole('button', { name: 'About valid date' }))
    expect(await screen.findByText('The business day the yield applies to, as published by the ECB.')).toBeInTheDocument()
  })

  it('shows the four key figures', async () => {
    await renderLoaded()
    await waitForMeasures()

    expectStatValue('10Y yield', /2\.600/)
    expectStatValue('2Y–10Y spread', '+52.1 bp')
    expectStatValue('3M–10Y spread', '+77.1 bp')
    expectStatValue('2Y–5Y–10Y curvature', '\u221212.1 bp')
    expect(screen.queryByText('Curve date')).toBeNull()
    expect(screen.queryByText('Knowledge')).toBeNull()
  })

  it('requests measures for the shown date at the curve answer\'s as_of', async () => {
    await renderLoaded()

    await waitFor(() =>
      expect(mockedMeasures).toHaveBeenCalledWith({
        curveId: 'ecb-aaa-spot',
        from: '2026-10-16',
        to: '2026-10-16',
        asOf: '2026-10-19T10:00:00Z',
      }),
    )
  })

  it('refetches measures for a picked date', async () => {
    await renderLoaded()

    pickDate('2026-10-01')

    await waitFor(() =>
      expect(mockedMeasures).toHaveBeenLastCalledWith(
        expect.objectContaining({ from: '2026-10-01', to: '2026-10-01' }),
      ),
    )
  })

  it('shows the Inverted badge when the curve is inverted', async () => {
    mockedMeasures.mockImplementation(async ({ from }) =>
      measuresResult(from, { spread_2y_10y: -15, inverted: true }),
    )
    await renderLoaded()

    expect(await screen.findByText('Inverted')).toBeInTheDocument()
    expectStatValue('2Y–10Y spread', '\u221215.0 bp')
    expect(statCard('2Y–10Y spread')).toContainElement(screen.getByText('Inverted'))
  })

  it('shows no Inverted badge otherwise', async () => {
    await renderLoaded()

    await waitFor(() => expectStatValue('2Y–10Y spread', '+52.1 bp'))
    expect(screen.queryByText('Inverted')).toBeNull()
  })

  it('explains a missing input', async () => {
    mockedMeasures.mockImplementation(async ({ from }) =>
      measuresResult(from, { curvature_2y_5y_10y: null, missing: ['5Y'] }),
    )
    await renderLoaded()
    await waitForMeasures()

    expectStatValue('2Y–5Y–10Y curvature', '–')
    expectStatHint('2Y–5Y–10Y curvature', 'No 5Y value')
  })

  it('shows Not available when the measures request fails', async () => {
    mockedMeasures.mockResolvedValue({ kind: 'offline' })
    await renderLoaded()

    expect(await screen.findAllByText('Not available')).toHaveLength(3)
    expect(screen.getByRole('heading', { name: 'Values' })).toBeInTheDocument()
    expect(screen.queryByRole('alert')).toBeNull()
  })

  it('shows flagged input hints', async () => {
    const warn = { status: 'warn' as const, flags: [] }
    mockedFetch.mockImplementation(async ({ validDate }) =>
      curveResult(validDate ?? '2026-10-16', [2.1, 2.4, 2.5, 2.6, null, null], [null, null, null, warn, null, null]),
    )
    mockedMeasures.mockImplementation(async ({ from }) =>
      measuresResult(from, { quality: { status: 'warn', flagged: ['10Y'] } }),
    )
    await renderLoaded()

    expect(await screen.findAllByText('Input flagged: 10Y')).toHaveLength(3)
    expectStatHint('10Y yield', 'Value flagged')
  })

  it('shows Not available for a missing 10Y', async () => {
    mockedFetch.mockImplementation(async ({ validDate }) =>
      curveResult(validDate ?? '2026-10-16', [2.1, 2.4, 2.5, null, null, null]),
    )
    await renderLoaded()

    expectStatValue('10Y yield', '–')
    expectStatHint('10Y yield', 'Not available')
  })

  it('shows skeletons while measures load', async () => {
    mockedMeasures.mockReturnValue(new Promise(() => {}))
    await renderLoaded()

    const grid = screen.getByText('10Y yield').closest('.mantine-SimpleGrid-root')
    expect(grid).toHaveAttribute('aria-busy', 'true')
    expect(grid!.querySelectorAll('.mantine-Skeleton-root')).toHaveLength(3)
    expectStatValue('10Y yield', /2\.600/)
  })

  it('each key figure has an explanation', async () => {
    await renderLoaded()

    for (const label of ['10Y yield', '2Y–10Y spread', '3M–10Y spread', '2Y–5Y–10Y curvature']) {
      expect(screen.getByRole('button', { name: `About ${label}` })).toBeInTheDocument()
    }
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
    render(<Host curve={AAA} />)

    expect(await screen.findByText('No value for: 15Y, 20Y')).toBeInTheDocument()
  })

  it('refetches for a picked date', async () => {
    render(<Host curve={AAA} />)
    const input = await screen.findByLabelText(/Valid date/)

    fireEvent.change(input, { target: { value: '2026-10-01' } })

    expect(mockedFetch).toHaveBeenLastCalledWith({ curveId: 'ecb-aaa-spot', validDate: '2026-10-01', asOf: undefined })
  })

  it('shows the offline state', async () => {
    mockedFetch.mockResolvedValue({ kind: 'offline' })

    render(<Host curve={AAA} />)

    expect(await screen.findByRole('alert')).toHaveTextContent('Backend offline')
  })

  it('passes asOf to the API', async () => {
    render(<Host curve={AAA} asOf="2026-10-01T12:00:00Z" />)

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
    render(<Host curve={AAA} asOf={asOf} />)

    expect(await screen.findByText(`No data known as of ${formatUtc(asOf)}`)).toBeInTheDocument()
  })

  it('overlays a second date', async () => {
    await renderLoaded()
    fireEvent.click(addButton())

    pickDate('2026-10-01')
    fireEvent.click(addButton())

    expect(mockedFetch).toHaveBeenCalledWith({ curveId: 'ecb-aaa-spot', validDate: '2026-10-01', asOf: undefined })
    const overlays = screen.getByRole('list', { name: 'Overlaid curves' })
    expect(within(overlays).getAllByRole('listitem')).toHaveLength(2)
    await waitFor(() =>
      expect(chartLabels()).toEqual(['ECB euro area AAA spot · 2026-10-01', 'ECB euro area AAA spot · 2026-10-16']),
    )
  })

  it('labels each pill with its curve and date', async () => {
    await renderLoaded()
    fireEvent.click(addButton())

    expect(await screen.findByRole('button', { name: 'Remove ECB euro area AAA spot · 2026-10-16 from overlay' })).toBeInTheDocument()
    expect(within(screen.getByRole('list', { name: 'Overlaid curves' })).getByText('ECB euro area AAA spot · 2026-10-16')).toBeInTheDocument()
  })

  it('removes an overlaid entry', async () => {
    await renderLoaded()
    fireEvent.click(addButton())
    pickDate('2026-10-01')
    fireEvent.click(addButton())

    fireEvent.click(await screen.findByRole('button', { name: 'Remove ECB euro area AAA spot · 2026-10-16 from overlay' }))

    await waitFor(() =>
      expect(
        screen.queryByRole('button', { name: 'Remove ECB euro area AAA spot · 2026-10-16 from overlay' }),
      ).not.toBeInTheDocument(),
    )
    await waitFor(() => expect(chartLabels()).toEqual(['ECB euro area AAA spot · 2026-10-01']))
  })

  it('moves focus to the next pill after a removal, or to the add button after the last', async () => {
    await renderLoaded()
    fireEvent.click(addButton())
    pickDate('2026-10-01')
    fireEvent.click(addButton())
    pickDate('2026-09-30')
    fireEvent.click(addButton())

    fireEvent.click(await screen.findByRole('button', { name: 'Remove ECB euro area AAA spot · 2026-10-16 from overlay' }))
    expect(screen.getByRole('button', { name: 'Remove ECB euro area AAA spot · 2026-10-01 from overlay' })).toHaveFocus()

    fireEvent.click(screen.getByRole('button', { name: 'Remove ECB euro area AAA spot · 2026-09-30 from overlay' }))
    expect(screen.getByRole('button', { name: 'Remove ECB euro area AAA spot · 2026-10-01 from overlay' })).toHaveFocus()

    fireEvent.click(screen.getByRole('button', { name: 'Remove ECB euro area AAA spot · 2026-10-01 from overlay' }))
    await waitFor(() => expect(addButton()).toHaveFocus())
  })

  it('announces additions and removals with the chart count', async () => {
    await renderLoaded()
    fireEvent.click(addButton())
    pickDate('2026-10-01')
    fireEvent.click(addButton())
    await waitFor(() => expect(chartLabels()).toContain('ECB euro area AAA spot · 2026-10-01'))

    expect(announcement()).toHaveTextContent(
      'Added ECB euro area AAA spot · 2026-10-01 to the overlay. 2 curves in the chart.',
    )
    fireEvent.click(screen.getByRole('button', { name: 'Remove ECB euro area AAA spot · 2026-10-16 from overlay' }))
    expect(announcement()).toHaveTextContent(
      'Removed ECB euro area AAA spot · 2026-10-16 from the overlay. 1 curve in the chart.',
    )
  })

  it('a pinned shown date is drawn once, in its entry colour', async () => {
    await renderLoaded()
    fireEvent.click(addButton())

    await waitFor(() => expect(mockedChart.mock.lastCall?.[0].curves).toHaveLength(1))
    expect(mockedChart.mock.lastCall?.[0].curves[0].slot).toBe(1)
    expect(mockedChart.mock.lastCall?.[0].curves[0].label).toBe('ECB euro area AAA spot · 2026-10-16')
  })

  it('explains why the add button is disabled for a pinned date', async () => {
    await renderLoaded()
    fireEvent.click(addButton())

    const hint = screen.getByText('This curve and date are already in the chart.')
    expect(addButton()).toBeDisabled()
    expect(addButton()).toHaveAttribute('aria-describedby', hint.id)
  })

  it('keeps entries when the curve changes, and fetches them on their own curve', async () => {
    const { rerender } = await renderLoaded()
    pickDate('2026-10-01')
    fireEvent.click(addButton())

    rerender(
      <>
        <Host curve={ALL} />
      </>,
    )

    expect(await screen.findByRole('list', { name: 'Overlaid curves' })).toHaveTextContent(
      'ECB euro area AAA spot · 2026-10-01',
    )
    await waitFor(() =>
      expect(chartLabels()).toEqual(['ECB euro area all-issuer spot · 2026-10-16', 'ECB euro area AAA spot · 2026-10-01']),
    )
    expect(mockedFetch).toHaveBeenCalledWith({ curveId: 'ecb-aaa-spot', validDate: '2026-10-01', asOf: undefined })
  })

  it('shows an alert for an entry that failed to load, and retries it', async () => {
    const { rerender } = await renderLoaded()
    pickDate('2026-10-01')
    fireEvent.click(addButton())
    pickDate('2026-10-16')
    mockedFetch.mockImplementation(async ({ validDate }) =>
      validDate === '2026-10-01'
        ? { kind: 'offline' }
        : curveResult(validDate ?? '2026-10-16', [2.1, 2.4, 2.5, 2.6, null, null]),
    )

    rerender(
      <>
        <Host curve={AAA} asOf={ASOF} />
      </>,
    )

    expect(await screen.findByRole('alert')).toHaveTextContent('Could not load ECB euro area AAA spot · 2026-10-01')
    mockedFetch.mockImplementation(async ({ validDate }) =>
      curveResult(validDate ?? '2026-10-16', [2.1, 2.4, 2.5, 2.6, null, null]),
    )
    fireEvent.click(screen.getByRole('button', { name: 'Try again' }))

    await waitFor(() => expect(screen.queryByRole('alert')).toBeNull())
    await waitFor(() => expect(chartLabels()).toContain('ECB euro area AAA spot · 2026-10-01'))
  })

  it('says when an entry has no data on its date', async () => {
    const { rerender } = await renderLoaded()
    pickDate('2026-09-01')
    fireEvent.click(addButton())
    pickDate('2026-10-16')
    mockedFetch.mockImplementation(async ({ validDate }) =>
      validDate === '2026-09-01'
        ? { kind: 'not-found', detail: 'none' }
        : curveResult(validDate ?? '2026-10-16', [2.1, 2.4, 2.5, 2.6, null, null]),
    )

    rerender(
      <>
        <Host curve={AAA} asOf={ASOF} />
      </>,
    )

    expect(await screen.findByText('No data for ECB euro area AAA spot on 2026-09-01.')).toBeInTheDocument()
    expect(screen.queryByRole('alert')).toBeNull()
  })

  it('shows an empty state for a date without data and keeps the requested date', async () => {
    await renderLoaded()
    mockedFetch.mockImplementation(async ({ validDate }) =>
      validDate === '2026-09-01'
        ? { kind: 'not-found', detail: 'none' }
        : curveResult(validDate ?? '2026-10-16', [2.1, 2.4, 2.5, 2.6, null, null]),
    )
    pickDate('2026-09-01')

    expect(await screen.findByText('No data for this date')).toBeInTheDocument()
    expect(screen.getByRole('status')).toHaveTextContent('No data for this date')
    expect(screen.getByLabelText(/Valid date/)).toHaveValue('2026-09-01')
    expect(screen.queryByRole('alert')).toBeNull()

    fireEvent.click(screen.getByRole('button', { name: 'Show latest date' }))
    await waitFor(() => expect(screen.queryByText('No data for this date')).toBeNull())
    expect(screen.getByLabelText(/Valid date/)).toHaveValue('2026-10-16')
  })

  it('refetches overlays when asOf changes', async () => {
    const { rerender } = await renderLoaded()
    fireEvent.click(addButton())
    pickDate('2026-10-01')
    fireEvent.click(addButton())
    const asOf = localInputToUtc('2026-10-01T12:00:00')

    rerender(
      <>
        <Host curve={AAA} asOf={asOf} />
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

  it('caps the overlay at 5 entries and says why the add button is disabled', async () => {
    await renderLoaded()
    const dates = ['2026-10-16', '2026-10-01', '2026-09-30', '2026-09-29', '2026-09-28']
    for (const date of dates) {
      pickDate(date)
      fireEvent.click(addButton())
    }

    const overlays = screen.getByRole('list', { name: 'Overlaid curves' })
    expect(within(overlays).getAllByRole('listitem')).toHaveLength(5)
    pickDate('2026-09-27')
    expect(addButton()).toBeDisabled()
    const hint = screen.getByText('The overlay holds 5 curves. Remove one to add another.')
    expect(addButton()).toHaveAttribute('aria-describedby', hint.id)
  })
})
