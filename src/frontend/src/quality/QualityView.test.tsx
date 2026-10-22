import { cleanup, fireEvent, render, screen, within } from '../test/render'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import type { components } from '../api/schema'
import { fetchQuality, type QualityResult } from './fetchQuality'
import QualityView from './QualityView'
import { AAA } from '../test/catalogue'

type QualityDay = components['schemas']['QualityDay']
type QualityFinding = components['schemas']['QualityFinding']
type RuleOutcome = components['schemas']['RuleOutcome']

vi.mock('./fetchQuality', () => ({
  fetchQuality: vi.fn(),
}))

const mockedFetch = vi.mocked(fetchQuality)

const ALL_PASSED: RuleOutcome[] = [
  { rule: 'range', outcome: 'passed', finding_count: 0 },
  { rule: 'jump', outcome: 'passed', finding_count: 0 },
  { rule: 'missing-date', outcome: 'passed', finding_count: 0 },
  { rule: 'missing-maturity', outcome: 'passed', finding_count: 0 },
]

function day(
  valid_date: string,
  status: QualityDay['status'],
  overrides: Partial<QualityDay> = {},
): QualityDay {
  return {
    valid_date,
    status,
    run_id: status === 'unchecked' ? null : 'run-2026-10-19',
    checked_as_of: status === 'unchecked' ? null : '2026-10-19T06:00:00Z',
    rules: ALL_PASSED,
    findings: [],
    ...overrides,
  }
}

function finding(
  rule: QualityFinding['rule'],
  severity: QualityFinding['severity'],
  maturity: string | null = null,
): QualityFinding {
  return {
    rule,
    severity,
    maturity,
    version_id: null,
    value: null,
    explanation: 'Why the rule exists.',
    evidence: 'What was found.',
  }
}

const jumpWarn = finding('jump', 'warn', '10Y')
const jumpInfo = finding('jump', 'info', '30Y')

const DAYS: QualityDay[] = [
  day('2026-10-07', 'unchecked', {
    rules: [
      { rule: 'range', outcome: 'unchecked', finding_count: 0 },
      { rule: 'jump', outcome: 'unchecked', finding_count: 0 },
      { rule: 'missing-date', outcome: 'unchecked', finding_count: 0 },
      { rule: 'missing-maturity', outcome: 'unchecked', finding_count: 0 },
    ],
  }),
  day('2026-10-08', 'passed', {
    rules: [
      { rule: 'range', outcome: 'passed', finding_count: 0 },
      { rule: 'jump', outcome: 'unchecked', finding_count: 0 },
      { rule: 'missing-date', outcome: 'passed', finding_count: 0 },
      { rule: 'missing-maturity', outcome: 'passed', finding_count: 0 },
    ],
  }),
  day('2026-10-09', 'warn', {
    rules: [
      { rule: 'range', outcome: 'passed', finding_count: 0 },
      { rule: 'jump', outcome: 'passed', finding_count: 0 },
      { rule: 'missing-date', outcome: 'warn', finding_count: 1 },
      { rule: 'missing-maturity', outcome: 'passed', finding_count: 0 },
    ],
    findings: [finding('missing-date', 'warn')],
  }),
  day('2026-10-16', 'warn', {
    rules: [
      { rule: 'range', outcome: 'passed', finding_count: 0 },
      { rule: 'jump', outcome: 'warn', finding_count: 2 },
      { rule: 'missing-date', outcome: 'passed', finding_count: 0 },
      { rule: 'missing-maturity', outcome: 'passed', finding_count: 0 },
    ],
    findings: [jumpInfo, jumpWarn],
  }),
]

function okResult(days: QualityDay[]): QualityResult {
  return {
    kind: 'ok',
    quality: {
      data: {
        curve_id: 'ecb-aaa-spot',
        valid_from: '2026-10-07',
        valid_to: '2026-10-16',
        days,
      },
      meta: {
        as_of: '2026-10-19T12:00:00Z',
        source_attribution: 'Source: ECB statistics',
      },
    },
  }
}

function dateCells() {
  const table = screen.getByRole('table')
  return within(table)
    .getAllByRole('row')
    .slice(1)
    .map((row) => within(row).getAllByRole('cell')[0].textContent)
}

beforeEach(() => {
  vi.useFakeTimers({ toFake: ['Date'] })
  vi.setSystemTime(new Date('2026-10-19T12:00:00Z'))
  mockedFetch.mockResolvedValue(okResult(DAYS))
})

afterEach(() => {
  cleanup()
  vi.clearAllMocks()
  vi.useRealTimers()
})

describe('QualityView', () => {
  it('shows skeletons and Loading… before the answer', () => {
    mockedFetch.mockReturnValue(new Promise(() => {}))
    const { container } = render(<QualityView curve={AAA} />)

    expect(screen.getByText('Loading…')).toBeInTheDocument()
    expect(container.querySelectorAll('.mantine-Skeleton-root')).toHaveLength(5)
  })

  it('shows stat cards from the days', async () => {
    render(<QualityView curve={AAA} />)

    expect(await screen.findByText('of 4 business days')).toBeInTheDocument()
    expect(screen.getByText('Days checked')).toBeInTheDocument()
    expect(screen.getByText('on 2 days')).toBeInTheDocument()
    expect(screen.getByText('Warnings')).toBeInTheDocument()
    expect(screen.getByText('Info flags')).toBeInTheDocument()
    expect(screen.getByText('on 1 days')).toBeInTheDocument()
    const lastCheck = screen.getByText('Last check').closest('.mantine-Card-root')
    expect(lastCheck).not.toBeNull()
    expect(within(lastCheck as HTMLElement).getByText('19 Oct 2026, 06:00:00 UTC')).toBeInTheDocument()
    expect(screen.queryByText('No check results known at this time')).toBeNull()
  })

  it('lists rows newest first with status badges', async () => {
    render(<QualityView curve={AAA} />)

    await screen.findByRole('cell', { name: '2026-10-16' })
    expect(dateCells()).toEqual(['2026-10-16', '2026-10-09', '2026-10-08', '2026-10-07'])
    const table = screen.getByRole('table')
    const firstRow = within(table).getAllByRole('row')[1]
    expect(within(firstRow).getByText('Warn')).toBeInTheDocument()
    expect(within(firstRow).getByRole('button', { name: 'Jump · warn, 10Y' })).toBeInTheDocument()
  })

  it('filter Warn keeps warn days; no match shows the filter empty state and Show all days restores', async () => {
    render(<QualityView curve={AAA} />)
    await screen.findByRole('cell', { name: '2026-10-16' })

    fireEvent.click(screen.getByRole('radio', { name: 'Warn' }))
    expect(dateCells()).toEqual(['2026-10-16', '2026-10-09'])

    fireEvent.click(screen.getByRole('radio', { name: 'Info' }))
    expect(screen.queryByRole('table')).toBeNull()
    expect(screen.getByRole('status')).toHaveTextContent('No days match this filter')

    fireEvent.click(screen.getByRole('button', { name: 'Show all days' }))
    expect(screen.getByRole('radio', { name: 'All' })).toBeChecked()
    expect(dateCells()).toHaveLength(4)
  })

  it('partial check shows Not checked: Jump', async () => {
    render(<QualityView curve={AAA} />)

    expect(await screen.findByText('Not checked: Jump')).toBeInTheDocument()
    expect(screen.getAllByText('Not checked: Jump')).toHaveLength(1)
  })

  it('empty days shows the empty state; Show last 30 days refetches the default range', async () => {
    mockedFetch.mockResolvedValueOnce(okResult([]))
    render(<QualityView curve={AAA} />)

    expect(await screen.findByText('No business days in this range')).toBeInTheDocument()
    expect(mockedFetch).toHaveBeenCalledTimes(1)

    mockedFetch.mockResolvedValueOnce(okResult(DAYS))
    fireEvent.click(screen.getByRole('button', { name: 'Show last 30 days' }))

    await screen.findByRole('cell', { name: '2026-10-16' })
    expect(mockedFetch).toHaveBeenCalledTimes(2)
    expect(mockedFetch).toHaveBeenLastCalledWith(
      expect.objectContaining({ from: '2026-09-19', to: '2026-10-19' }),
    )
  })

  it('404 shows No quality results for this curve', async () => {
    mockedFetch.mockResolvedValue({ kind: 'not-found', detail: 'No quality results.' })
    render(<QualityView curve={AAA} />)

    expect(await screen.findByText('No quality results for this curve')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Show last 30 days' })).toBeInTheDocument()
  })

  it('offline shows Backend offline and Try again refetches', async () => {
    mockedFetch.mockResolvedValueOnce({ kind: 'offline' })
    render(<QualityView curve={AAA} />)

    expect(await screen.findByRole('alert')).toHaveTextContent('Backend offline')
    fireEvent.click(screen.getByRole('button', { name: 'Try again' }))

    await screen.findByRole('cell', { name: '2026-10-16' })
    expect(mockedFetch).toHaveBeenCalledTimes(2)
  })

  it('422 shows detail under Could not load quality results', async () => {
    mockedFetch.mockResolvedValue({ kind: 'invalid', detail: 'The range is not valid.' })
    render(<QualityView curve={AAA} />)

    const alert = await screen.findByRole('alert')
    expect(alert).toHaveTextContent('Could not load quality results')
    expect(alert).toHaveTextContent('The range is not valid.')
  })

  it('To before From shows the error and does not fetch', async () => {
    render(<QualityView curve={AAA} />)
    await screen.findByRole('cell', { name: '2026-10-16' })
    mockedFetch.mockClear()

    fireEvent.change(screen.getByLabelText('To'), { target: { value: '2026-09-01' } })

    expect(screen.getByText('To must be on or after From.')).toBeInTheDocument()
    expect(mockedFetch).not.toHaveBeenCalled()
  })

  it('names the curve in the subtitle', async () => {
    render(<QualityView curve={AAA} />)

    expect(
      await screen.findByText('Plausibility and completeness checks per business day, ECB euro area AAA spot'),
    ).toBeInTheDocument()
  })

  it('range over 366 days shows the error and does not fetch', async () => {
    render(<QualityView curve={AAA} />)
    await screen.findByRole('cell', { name: '2026-10-16' })
    mockedFetch.mockClear()

    fireEvent.change(screen.getByLabelText('From'), { target: { value: '2025-10-16' } })

    expect(screen.getByText('Choose a range of at most 366 days.')).toBeInTheDocument()
    expect(mockedFetch).not.toHaveBeenCalled()
  })
})
