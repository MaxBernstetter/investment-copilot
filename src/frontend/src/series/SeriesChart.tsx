import { lazy, Suspense } from 'react'
import { Skeleton } from '@mantine/core'
import { CHART_COLORS } from '../theme'
import { seriesChart, type SeriesPoint } from './seriesData'

const LineChart = lazy(() => import('@mantine/charts').then((m) => ({ default: m.LineChart })))

type SeriesChartProps = {
  points: SeriesPoint[]
}

export default function SeriesChart({ points }: SeriesChartProps) {
  return (
    <Suspense fallback={<Skeleton h={320} />}>
      <LineChart
        h={320}
        data={seriesChart(points)}
        dataKey="valid_date"
        series={[{ name: 'value', label: 'Yield', color: CHART_COLORS[0] }]}
        curveType="linear"
        strokeWidth={2}
        gridAxis="y"
        yAxisProps={{ domain: ['auto', 'auto'] }}
        connectNulls={false}
        withDots={points.length <= 15}
        withBrush
        withLegend={false}
        valueFormatter={(value) => value.toFixed(3)}
        tooltipAnimationDuration={0}
        lineProps={{ isAnimationActive: false }}
        xAxisProps={{ minTickGap: 32 }}
      />
    </Suspense>
  )
}
