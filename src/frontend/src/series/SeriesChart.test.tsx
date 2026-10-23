import { LineChart } from '@mantine/charts'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { cleanup, render, waitFor } from '../test/render'
import SeriesChart from './SeriesChart'

vi.mock('@mantine/charts', () => ({
  LineChart: vi.fn(() => null),
}))

const mockedLineChart = vi.mocked(LineChart)

const rows = [
  { valid_date: '2026-10-15', value: 2.89 },
  { valid_date: '2026-10-16', value: null },
]

afterEach(() => {
  cleanup()
  vi.clearAllMocks()
})

describe('SeriesChart', () => {
  it('formats yield values with three decimals and no unit, with the default ticks', async () => {
    render(<SeriesChart rows={rows} label="Yield" decimals={3} />)

    await waitFor(() => expect(mockedLineChart).toHaveBeenCalled())
    const props = mockedLineChart.mock.calls[0][0]
    expect(props.unit).toBeUndefined()
    expect(props.valueFormatter?.(2.89)).toBe('2.890')
    expect(props.yAxisProps?.tickFormatter).toBeUndefined()
  })

  it('formats bp measure values and ticks with one decimal', async () => {
    render(<SeriesChart rows={rows} label="2Y–10Y spread" decimals={1} />)

    await waitFor(() => expect(mockedLineChart).toHaveBeenCalled())
    const props = mockedLineChart.mock.calls[0][0]
    expect(props.valueFormatter?.(-15)).toBe('-15.0')
    expect(props.yAxisProps?.tickFormatter?.(2.89, 0)).toBe('2.9')
  })

  it('names the series, leaves gaps at null values and dots only up to 15 rows', async () => {
    render(<SeriesChart rows={rows} label="2Y–10Y spread" decimals={1} />)

    await waitFor(() => expect(mockedLineChart).toHaveBeenCalled())
    const props = mockedLineChart.mock.calls[0][0]
    expect(props.series).toEqual([expect.objectContaining({ name: 'value', label: '2Y–10Y spread' })])
    expect(props.data).toEqual(rows)
    expect(props.connectNulls).toBe(false)
    expect(props.withDots).toBe(true)
  })

  it('draws a dashed, dimmed 0 bp line only when asked for, with the y domain still automatic', async () => {
    render(<SeriesChart rows={rows} label="2Y–10Y spread" decimals={1} zeroLine />)

    await waitFor(() => expect(mockedLineChart).toHaveBeenCalled())
    const props = mockedLineChart.mock.calls[0][0]
    expect(props.referenceLines).toEqual([
      expect.objectContaining({
        y: 0,
        color: 'var(--mantine-color-dimmed)',
        strokeDasharray: '4 4',
        label: '0 bp',
      }),
    ])
    expect(props.yAxisProps?.domain).toEqual(['auto', 'auto'])
  })

  it('has no reference line for yields or curvature', async () => {
    render(<SeriesChart rows={rows} label="2Y–5Y–10Y curvature" decimals={1} />)

    await waitFor(() => expect(mockedLineChart).toHaveBeenCalled())
    expect(mockedLineChart.mock.calls[0][0].referenceLines).toBeUndefined()
  })
})
