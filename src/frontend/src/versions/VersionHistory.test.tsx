import { cleanup, fireEvent, render, screen, waitFor, within } from '../test/render'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import type { components } from '../api/schema'
import { fetchVersions, type VersionsResult } from './fetchVersions'
import VersionHistory from './VersionHistory'

vi.mock('./fetchVersions', () => ({
  fetchVersions: vi.fn(),
}))

const mockedFetch = vi.mocked(fetchVersions)

type Version = components['schemas']['ValueVersion']

const first: Version = {
  version_id: 1,
  value: 2.4,
  known_from: '2026-10-16T08:00:00Z',
  known_to: '2026-10-17T08:00:00Z',
  source_id: 'ecb',
  run_id: 'run-1',
  change_reason: 'initial',
  normalization_version: '1',
  delivery_id: '4711',
}

const second: Version = {
  version_id: 2,
  value: 2.5,
  known_from: '2026-10-17T08:00:00Z',
  known_to: null,
  source_id: null,
  run_id: 'run-2',
  change_reason: 'revision',
  normalization_version: null,
  delivery_id: null,
}

function okResult(versions: Version[]): VersionsResult {
  return {
    kind: 'ok',
    versions: {
      data: {
        curve_id: 'ecb-aaa-spot',
        maturity: '10Y',
        valid_date: '2026-10-16',
        versions,
      },
      meta: { as_of: '2026-10-19T10:00:00Z', source_attribution: 'Source: ECB statistics' },
    },
  }
}

beforeEach(() => {
  mockedFetch.mockResolvedValue(okResult([first, second]))
})

afterEach(() => {
  cleanup()
  vi.clearAllMocks()
})

function renderHistory(props: { asOf?: string } = {}) {
  const onClose = vi.fn()
  render(
    <VersionHistory curveId="ecb-aaa-spot" maturity="10Y" validDate="2026-10-16" onClose={onClose} {...props} />,
  )
  return { onClose }
}

function rows(): string[][] {
  const table = screen.getByRole('table')
  return within(table)
    .getAllByRole('row')
    .slice(1)
    .map((row) => within(row).getAllByRole('cell').map((cell) => cell.textContent ?? ''))
}

describe('VersionHistory', () => {
  it('shows every version oldest first with reason and source', async () => {
    renderHistory()

    expect(await screen.findByRole('table')).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'History of 10Y on 2026-10-16' })).toBeInTheDocument()
    expect(rows()).toEqual([
      ['2.4', new Date(first.known_from).toUTCString(), new Date(first.known_to ?? '').toUTCString(), 'initial', 'ecb', 'run-1', '4711'],
      ['2.5', new Date(second.known_from).toUTCString(), 'current', 'revision', '–', 'run-2', '–'],
    ])
  })

  it('shows current for the open version', async () => {
    renderHistory()

    const cells = (await screen.findAllByRole('cell')).map((cell) => cell.textContent)
    expect(cells).toContain('current')
    expect(screen.getAllByRole('cell').filter((cell) => cell.textContent === 'current')).toHaveLength(1)
  })

  it('sends as_of and valid date', async () => {
    renderHistory({ asOf: '2026-10-18T12:00:00Z' })

    await screen.findByRole('table')
    expect(mockedFetch).toHaveBeenCalledWith({
      curveId: 'ecb-aaa-spot',
      maturity: '10Y',
      validDate: '2026-10-16',
      asOf: '2026-10-18T12:00:00Z',
    })
  })

  it('shows not-found and offline states', async () => {
    mockedFetch.mockResolvedValueOnce({ kind: 'not-found', detail: 'no value' })
    const { unmount } = render(
      <VersionHistory curveId="ecb-aaa-spot" maturity="10Y" validDate="2026-10-16" onClose={vi.fn()} />,
    )
    expect(await screen.findByRole('status')).toHaveTextContent('No data known for this value.')
    unmount()

    mockedFetch.mockResolvedValueOnce({ kind: 'offline' })
    renderHistory()
    expect(await screen.findByRole('alert')).toHaveTextContent('Backend offline')
  })

  it('calls onClose from the Close button', async () => {
    const { onClose } = renderHistory()

    await screen.findByRole('table')
    fireEvent.click(screen.getByRole('button', { name: 'Close' }))

    await waitFor(() => expect(onClose).toHaveBeenCalledTimes(1))
  })
})
