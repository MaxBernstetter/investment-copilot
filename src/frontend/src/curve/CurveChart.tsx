import { lazy, Suspense } from 'react'
import { Skeleton } from '@mantine/core'
import { overlayRows, overlaySeries, type LabelledCurve } from './curveData'

const LineChart = lazy(() => import('@mantine/charts').then((m) => ({ default: m.LineChart })))

type CurveChartProps = {
  curves: LabelledCurve[]
}

export default function CurveChart({ curves }: CurveChartProps) {
  return (
    <Suspense fallback={<Skeleton h={320} />}>
      <LineChart
        h={320}
        data={overlayRows(curves)}
        dataKey="maturity"
        series={overlaySeries(curves)}
        connectNulls={false}
        withLegend
        curveType="linear"
        unit="%"
        yAxisLabel="Yield (%)"
      />
    </Suspense>
  )
}
