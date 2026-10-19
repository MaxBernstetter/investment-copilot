import { describe, expect, it } from 'vitest'
import { formatDeltaBp, toChangeRows, type ValueChange } from './changesData'

const correction: ValueChange = {
  valid_date: '2026-10-16',
  maturity: '10Y',
  old_value: 26.4,
  new_value: 2.64,
  change_reason: 'correction',
  source_id: 'ecb',
  known_from: '2026-10-18T08:00:00Z',
}

const firstKnownLater: ValueChange = {
  valid_date: '2026-10-15',
  maturity: '3M',
  old_value: null,
  new_value: 2.5,
  change_reason: 'initial',
  source_id: null,
  known_from: '2026-10-17T08:00:00Z',
}

describe('changesData', () => {
  it('formats a correction as signed basis points', () => {
    expect(formatDeltaBp(26.4, 2.64)).toBe('-2376.0 bp')
    expect(toChangeRows([correction])[0].delta).toBe('-2376.0 bp')
  })

  it('shows a dash for a value first known later', () => {
    const [row] = toChangeRows([firstKnownLater])

    expect(formatDeltaBp(null, 2.5)).toBe('–')
    expect(row).toMatchObject({ oldValue: '–', delta: '–', source: '–', newValue: '2.5' })
    expect(row.knownFrom).toBe(new Date('2026-10-17T08:00:00Z').toUTCString())
  })

  it('keeps the API order', () => {
    const rows = toChangeRows([correction, firstKnownLater])

    expect(rows.map((row) => row.key)).toEqual(['2026-10-16-10Y', '2026-10-15-3M'])
  })
})
