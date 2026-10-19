import { useEffect, useRef } from 'react'
import Plotly from 'plotly.js-dist-min'
import { seriesChart, type SeriesPoint } from './seriesData'

type SeriesChartProps = {
  points: SeriesPoint[]
}

export default function SeriesChart({ points }: SeriesChartProps) {
  const ref = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const div = ref.current
    if (!div) return
    const { x, y } = seriesChart(points)
    void Plotly.react(
      div,
      [{ x, y, type: 'scatter', mode: 'lines+markers' }],
      {
        xaxis: { type: 'date' },
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
