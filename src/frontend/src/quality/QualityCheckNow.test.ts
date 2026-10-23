import { describe, expect, it } from 'vitest'
import { checkEnd, checkSummary } from './QualityCheckNow'

describe('checkEnd', () => {
  const now = new Date('2026-10-23T12:00:00Z')

  it('stops at yesterday when the range reaches today', () => {
    expect(checkEnd('2026-09-23', '2026-10-23', now)).toBe('2026-10-22')
  })

  it('keeps an earlier end', () => {
    expect(checkEnd('2026-09-01', '2026-10-01', now)).toBe('2026-10-01')
  })

  it('never ends before the start', () => {
    expect(checkEnd('2026-10-23', '2026-10-23', now)).toBe('2026-10-23')
  })
})

describe('checkSummary', () => {
  it('names the range and the counts', () => {
    expect(
      checkSummary(
        { days: 3, values: 33, warn_count: 1, info_count: 2, checked_as_of: '2026-10-19T12:00:00Z' },
        '2026-10-01',
        '2026-10-07',
      ),
    ).toBe('Checked 2026-10-01 to 2026-10-07: 3 business days and 33 values, 1 warnings, 2 info flags.')
  })
})
