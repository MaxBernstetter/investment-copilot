import { describe, expect, it } from 'vitest'
import { formatBp, formatUtc, formatYield } from './format'

describe('formatUtc', () => {
  it('formats an instant in UTC with seconds', () => {
    expect(formatUtc('2026-10-19T18:49:25Z')).toBe('19 Oct 2026, 18:49:25 UTC')
  })

  it('pads the time and keeps a single-digit day unpadded', () => {
    expect(formatUtc('2026-01-02T03:04:05.678Z')).toBe('2 Jan 2026, 03:04:05 UTC')
  })

  it('drops the seconds on request', () => {
    expect(formatUtc('2026-10-19T18:49:25Z', 'minutes')).toBe('19 Oct 2026, 18:49 UTC')
  })
})

describe('formatBp', () => {
  it('signs positive changes with a plus and one decimal', () => {
    expect(formatBp(9)).toBe('+9.0 bp')
    expect(formatBp(71.34)).toBe('+71.3 bp')
  })

  it('uses a true minus and a thousands separator for negative changes', () => {
    expect(formatBp(-2376)).toBe('−2,376.0 bp')
    expect(formatBp(-9.04)).toBe('−9.0 bp')
    expect(formatBp(-0.5)).toBe('−0.5 bp')
  })

  it('shows zero without a sign', () => {
    expect(formatBp(0)).toBe('0.0 bp')
    expect(formatBp(0.04)).toBe('0.0 bp')
  })

  it('groups thousands in large values', () => {
    expect(formatBp(1234567.8)).toBe('+1,234,567.8 bp')
  })
})

describe('formatYield', () => {
  it('shows three decimals and a narrow no-break space before the percent sign', () => {
    expect(formatYield(2.871)).toBe('2.871 %')
    expect(formatYield(2.7)).toBe('2.700 %')
  })

  it('rounds to three decimals', () => {
    expect(formatYield(3.4444646497)).toBe('3.444 %')
    expect(formatYield(2.871)).toContain('\u202F%')
  })
})
