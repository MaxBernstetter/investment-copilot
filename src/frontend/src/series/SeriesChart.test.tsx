import { LineChart } from '@mantine/charts'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { cleanup, render, waitFor } from '../test/render'
import SeriesChart from './SeriesChart'
import type { SeriesPoint } from './seriesData'

vi.mock('@mantine/charts', () => ({
  LineChart: vi.fn(() => null),
}))

const mockedLineChart = vi.mocked(LineChart)

const point: SeriesPoint = {
  valid_date: '2026-10-16',
  value: 2.89,
  version_id: 1,
  origin: 'published',
  quality: { status: 'passed', flags: [] },
}

afterEach(() => {
  cleanup()
  vi.clearAllMocks()
})

describe('SeriesChart', () => {
  it('formats y values with three decimals and no unit', async () => {
    render(<SeriesChart points={[point]} />)

    await waitFor(() => expect(mockedLineChart).toHaveBeenCalled())
    const props = mockedLineChart.mock.calls[0][0]
    expect(props.unit).toBeUndefined()
    expect(props.valueFormatter?.(2.89)).toBe('2.890')
  })
})
