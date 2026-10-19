import { useEffect, useState } from 'react'
import CurveChart from './CurveChart'
import { missingMaturities } from './curveData'
import { fetchCurve, type CurveResult } from './fetchCurve'

export default function CurveView() {
  const [validDate, setValidDate] = useState<string | undefined>(undefined)
  const [result, setResult] = useState<CurveResult | undefined>(undefined)

  useEffect(() => {
    let active = true
    fetchCurve({ validDate }).then((next) => {
      if (active) setResult(next)
    })
    return () => {
      active = false
    }
  }, [validDate])

  const returnedDate = result?.kind === 'ok' ? result.curve.data.valid_date : ''
  const missing = result?.kind === 'ok' ? missingMaturities(result.curve.data.points) : []

  return (
    <section>
      <h2>ECB euro area AAA spot curve</h2>
      <label>
        Valid date{' '}
        <input
          type="date"
          value={validDate ?? returnedDate}
          onChange={(event) => setValidDate(event.target.value || undefined)}
        />
      </label>
      {result === undefined && <p>Loading…</p>}
      {result?.kind === 'ok' && (
        <>
          <CurveChart points={result.curve.data.points} />
          {missing.length > 0 && <p>No value for: {missing.join(', ')}</p>}
        </>
      )}
      {result?.kind === 'offline' && (
        <p role="alert">Backend offline: the YieldLens API is not reachable. Try again later.</p>
      )}
      {result?.kind === 'not-found' && <p role="status">No data known for this date.</p>}
      {(result?.kind === 'invalid' || result?.kind === 'error') && (
        <p role="alert">{result.detail}</p>
      )}
      <p>
        Source: <a href="https://data.ecb.europa.eu/">ECB statistics</a>
      </p>
    </section>
  )
}
