import { afterEach, describe, expect, it, vi } from 'vitest'
import { defaultRange, seriesChart, type SeriesPoint } from './seriesData'

afterEach(() => {
  vi.useRealTimers()
})

describe('seriesData', () => {
  it('defaultRange spans 365 days', () => {
    const { from, to } = defaultRange(new Date('2026-10-19T12:00:00Z'))

    expect(from).toBe('2025-10-19')
    expect(to).toBe('2026-10-19')
    expect((Date.parse(to) - Date.parse(from)) / (24 * 60 * 60 * 1000)).toBe(365)
  })

  it('series rows in valid-date order', () => {
    const points: SeriesPoint[] = [
      { valid_date: '2026-10-15', value: 2.5, version_id: 1, origin: 'published' },
      { valid_date: '2026-10-16', value: 2.6, version_id: 2, origin: 'published' },
      { valid_date: '2026-10-19', value: 2.7, version_id: 3, origin: 'published' },
    ]

    expect(seriesChart(points)).toEqual([
      { valid_date: '2026-10-15', value: 2.5 },
      { valid_date: '2026-10-16', value: 2.6 },
      { valid_date: '2026-10-19', value: 2.7 },
    ])
  })
})
