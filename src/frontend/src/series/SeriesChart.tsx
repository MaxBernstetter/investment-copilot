import { lazy, Suspense } from 'react'
import { Skeleton } from '@mantine/core'
import { CHART_COLORS } from '../theme'

const LineChart = lazy(() => import('@mantine/charts').then((m) => ({ default: m.LineChart })))

export type ChartRow = { valid_date: string; value: number | null }

type SeriesChartProps = {
  /** Valid-date order; a null value leaves a gap in the line. */
  rows: ChartRow[]
  /** The series name in the tooltip. */
  label: string
  /** Decimals for the tooltip and, for bp measures, the axis ticks. */
  decimals: 1 | 3
  /** A dashed, dimmed line at 0 bp (spreads only, #258 MR3). The y domain stays auto. */
  zeroLine?: boolean
}

const ZERO_LINE = [
  {
    y: 0,
    color: 'var(--mantine-color-dimmed)',
    strokeDasharray: '4 4',
    strokeWidth: 1,
    label: '0 bp',
    labelPosition: 'insideBottomRight' as const,
  },
]

const formatFixed = (decimals: number) => (value: number) => value.toFixed(decimals)

export default function SeriesChart({ rows, label, decimals, zeroLine = false }: SeriesChartProps) {
  // Yield axes keep Mantine's default ticks; bp measures show ticks at one decimal, like the tooltip.
  const yAxisProps = {
    domain: ['auto', 'auto'] as ['auto', 'auto'],
    ...(decimals === 1 ? { tickFormatter: formatFixed(1) } : {}),
  }
  return (
    <Suspense fallback={<Skeleton h={320} />}>
      <LineChart
        h={320}
        data={rows}
        dataKey="valid_date"
        series={[{ name: 'value', label, color: CHART_COLORS[0] }]}
        curveType="linear"
        strokeWidth={2}
        gridAxis="y"
        yAxisProps={yAxisProps}
        referenceLines={zeroLine ? ZERO_LINE : undefined}
        connectNulls={false}
        withDots={rows.length <= 15}
        withBrush
        withLegend={false}
        valueFormatter={formatFixed(decimals)}
        tooltipAnimationDuration={0}
        lineProps={{ isAnimationActive: false }}
        xAxisProps={{ minTickGap: 32 }}
      />
    </Suspense>
  )
}
