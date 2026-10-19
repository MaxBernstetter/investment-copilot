import { useEffect, useState } from 'react'
import { readAsOf, writeAsOf } from '../asOf'
import AsOfControl from './AsOfControl'
import CurveChart from './CurveChart'
import { missingMaturities } from './curveData'
import { fetchCurve, type CurveResult } from './fetchCurve'

export default function CurveView() {
  const [validDate, setValidDate] = useState<string | undefined>(undefined)
  const [asOf, setAsOf] = useState<string | undefined>(() => readAsOf(window.location.search))
  const [result, setResult] = useState<CurveResult | undefined>(undefined)

  useEffect(() => {
    let active = true
    fetchCurve({ validDate, asOf }).then((next) => {
      if (active) setResult(next)
    })
    return () => {
      active = false
    }
  }, [validDate, asOf])

  const changeAsOf = (next: string | undefined) => {
    setAsOf(next)
    writeAsOf(next)
  }

  const returnedDate = result?.kind === 'ok' ? result.curve.data.valid_date : ''
  const missing = result?.kind === 'ok' ? missingMaturities(result.curve.data.points) : []
  const asOfText = asOf ? new Date(asOf).toUTCString() : ''

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
      <AsOfControl asOf={asOf} onChange={changeAsOf} />
      {asOf && <p role="status">Showing the curve as known on {asOfText}</p>}
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
      {result?.kind === 'not-found' && !asOf && (
        <p role="status">No data known for this date.</p>
      )}
      {result?.kind === 'not-found' && asOf && <p>No data known as of {asOfText}</p>}
      {(result?.kind === 'invalid' || result?.kind === 'error') && (
        <p role="alert">{result.detail}</p>
      )}
      <p>
        Source: <a href="https://data.ecb.europa.eu/">ECB statistics</a>
      </p>
    </section>
  )
}
