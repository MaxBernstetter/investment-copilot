import { describe, expect, it } from 'vitest'
import { formatBp, formatYield } from '../format'
import { toChangeRows, type ValueChange } from './changesData'

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
  it('formats a correction as signed basis points with a true minus', () => {
    const delta = formatBp((2.64 - 26.4) * 100)
    expect(delta).toBe('−2,376.0 bp')
    expect(toChangeRows([correction])[0].delta).toBe(delta)
  })

  it('shows a dash for a value first known later', () => {
    const [row] = toChangeRows([firstKnownLater])

    expect(row).toMatchObject({
      oldValue: '–',
      delta: '–',
      source: '–',
      newValue: formatYield(2.5),
    })
    expect(row.knownFrom).toBe('17 Oct 2026, 08:00:00 UTC')
  })

  it('keeps the API order', () => {
    const rows = toChangeRows([correction, firstKnownLater])

    expect(rows.map((row) => row.key)).toEqual(['2026-10-16-10Y', '2026-10-15-3M'])
  })
})
