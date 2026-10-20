import { describe, expect, it } from 'vitest'
import { seriesStats, type SeriesPoint } from './seriesData'

const point = (valid_date: string, value: number): SeriesPoint => ({
  valid_date,
  value,
  version_id: 1,
  origin: 'published',
  quality: { status: 'passed', flags: [] },
})

describe('seriesData', () => {
  it('summarises last, min, max and signed change in bp', () => {
    expect(seriesStats([point('2026-10-01', 2.5), point('2026-10-16', 2.6)])).toEqual({
      last: 2.6,
      min: 2.5,
      max: 2.6,
      changeBp: 10,
    })
    expect(seriesStats([point('2026-10-01', 3), point('2026-10-16', 2.5)]).changeBp).toBe(-50)
  })

  it('leaves change undefined with fewer than two points', () => {
    expect(seriesStats([point('2026-10-16', 2.6)]).changeBp).toBeUndefined()
    expect(seriesStats([]).last).toBeUndefined()
  })
})
