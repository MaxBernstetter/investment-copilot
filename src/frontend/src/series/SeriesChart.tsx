import { lazy, Suspense } from 'react'
import { Skeleton } from '@mantine/core'
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
        series={[{ name: 'value', label: 'Yield', color: 'indigo.6' }]}
        withDots={false}
        withBrush
        xAxisProps={{ minTickGap: 32 }}
        unit="%"
      />
    </Suspense>
  )
}
