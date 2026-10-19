import { useEffect, useRef } from 'react'
import Plotly from 'plotly.js-dist-min'
import { overlayTraces, type LabelledCurve } from './curveData'

type CurveChartProps = {
  curves: LabelledCurve[]
}

export default function CurveChart({ curves }: CurveChartProps) {
  const ref = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const div = ref.current
    if (!div) return
    const data = overlayTraces(curves).map((trace) => ({
      ...trace,
      type: 'scatter' as const,
      mode: 'lines+markers' as const,
      connectgaps: false,
      showlegend: true,
    }))
    void Plotly.react(div, data, {
      xaxis: { type: 'category', title: { text: 'Maturity' } },
      yaxis: { title: { text: 'Yield (%)' } },
      margin: { t: 16 },
    })
  }, [curves])

  useEffect(() => {
    const div = ref.current
    return () => {
      if (div) Plotly.purge(div)
    }
  }, [])

  return <div ref={ref} />
}
