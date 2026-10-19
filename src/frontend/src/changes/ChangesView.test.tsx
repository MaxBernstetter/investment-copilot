import { cleanup, fireEvent, render, screen } from '../test/render'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import type { components } from '../api/schema'
import { localInputToUtc } from '../asOf'
import { fetchChanges, type ChangesResult } from './fetchChanges'
import ChangesView from './ChangesView'

type ValueChange = components['schemas']['ValueChange']

vi.mock('./fetchChanges', () => ({
  fetchChanges: vi.fn(),
}))

const mockedFetch = vi.mocked(fetchChanges)

const SINCE_INPUT = '2026-10-17T08:00:00'

function okResult(changes: ValueChange[]): ChangesResult {
  return {
    kind: 'ok',
    changes: {
      data: {
        curve_id: 'ecb-aaa-spot',
        valid_from: '2025-10-19',
        valid_to: '2026-10-19',
        changes,
      },
      meta: { since: '2026-10-17T08:00:00Z', as_of: '2026-10-19T10:00:00Z' },
    },
  }
}

const correction: ValueChange = {
  valid_date: '2026-10-16',
  maturity: '10Y',
  old_value: 2.61,
  new_value: 2.7,
  change_reason: 'correction',
  source_id: 'ecb',
  known_from: '2026-10-18T08:00:00Z',
}

beforeEach(() => {
  vi.useFakeTimers({ toFake: ['Date'] })
  vi.setSystemTime(new Date('2026-10-19T12:00:00Z'))
  mockedFetch.mockResolvedValue(okResult([correction]))
})

afterEach(() => {
  cleanup()
  vi.clearAllMocks()
  vi.useRealTimers()
  window.history.replaceState(null, '', '/')
})

describe('ChangesView', () => {
  it('asks for the earlier knowledge time before fetching', () => {
    render(<ChangesView curveId="ecb-aaa-spot" />)

    expect(screen.getByRole('status')).toHaveTextContent('Choose the earlier knowledge time to compare.')
    expect(mockedFetch).not.toHaveBeenCalled()
  })

  it('shows old value, new value, change and reason', async () => {
    render(<ChangesView curveId="ecb-aaa-spot" />)

    fireEvent.change(screen.getByLabelText('Compare from (known as of)'), { target: { value: SINCE_INPUT } })

    expect(await screen.findByRole('cell', { name: '2.61' })).toBeInTheDocument()
    expect(screen.getByRole('cell', { name: '2.7' })).toBeInTheDocument()
    expect(screen.getByRole('cell', { name: '+9.0 bp' })).toBeInTheDocument()
    expect(screen.getByText('correction')).toBeInTheDocument()
  })

  it('passes curve, range, since and as_of to the fetch', async () => {
    window.history.replaceState(null, '', '/?as_of=2026-10-18T09:00:00Z')
    render(<ChangesView curveId="ecb-aaa-spot" />)

    fireEvent.change(screen.getByLabelText('Compare from (known as of)'), { target: { value: SINCE_INPUT } })

    expect(await screen.findByRole('cell', { name: '2.7' })).toBeInTheDocument()
    expect(mockedFetch).toHaveBeenLastCalledWith({
      curveId: 'ecb-aaa-spot',
      from: '2025-10-19',
      to: '2026-10-19',
      since: localInputToUtc(SINCE_INPUT),
      asOf: '2026-10-18T09:00:00Z',
    })
  })

  it('shows that nothing changed', async () => {
    mockedFetch.mockResolvedValue(okResult([]))
    render(<ChangesView curveId="ecb-aaa-spot" />)

    fireEvent.change(screen.getByLabelText('Compare from (known as of)'), { target: { value: SINCE_INPUT } })

    expect(await screen.findByText('No changes between these knowledge times.')).toBeInTheDocument()
  })

  it('shows the offline alert', async () => {
    mockedFetch.mockResolvedValue({ kind: 'offline' })
    render(<ChangesView curveId="ecb-aaa-spot" />)

    fireEvent.change(screen.getByLabelText('Compare from (known as of)'), { target: { value: SINCE_INPUT } })

    expect(await screen.findByRole('alert')).toHaveTextContent(
      'Backend offline: the YieldLens API is not reachable. Try again later.',
    )
  })
})
