import { useEffect, useRef } from 'react'
import Plotly from 'plotly.js-dist-min'
import { chartSeries, type CurvePoint } from './curveData'

type CurveChartProps = {
  points: CurvePoint[]
}

export default function CurveChart({ points }: CurveChartProps) {
  const ref = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const div = ref.current
    if (!div) return
    const { x, y } = chartSeries(points)
    void Plotly.react(
      div,
      [{ x, y, type: 'scatter', mode: 'lines+markers', connectgaps: false }],
      {
        xaxis: { type: 'category', title: { text: 'Maturity' } },
        yaxis: { title: { text: 'Yield (%)' } },
        margin: { t: 16 },
      },
    )
  }, [points])

  useEffect(() => {
    const div = ref.current
    return () => {
      if (div) Plotly.purge(div)
    }
  }, [])

  return <div ref={ref} />
}
