import { useEffect, useState } from 'react'
import { readAsOf, writeAsOf } from '../asOf'
import AsOfControl from '../curve/AsOfControl'
import { fetchSeries, type SeriesResult } from './fetchSeries'
import SeriesChart from './SeriesChart'
import { defaultRange, MATURITIES } from './seriesData'

const DEFAULT_MATURITY = '10Y'

export default function SeriesView() {
  const [maturity, setMaturity] = useState(DEFAULT_MATURITY)
  const [range, setRange] = useState(() => defaultRange(new Date()))
  const [asOf, setAsOf] = useState<string | undefined>(() => readAsOf(window.location.search))
  const [result, setResult] = useState<SeriesResult | undefined>(undefined)

  useEffect(() => {
    let active = true
    fetchSeries({ maturity, from: range.from, to: range.to, asOf }).then((next) => {
      if (active) setResult(next)
    })
    return () => {
      active = false
    }
  }, [maturity, range, asOf])

  const changeAsOf = (next: string | undefined) => {
    setAsOf(next)
    writeAsOf(next)
  }

  const asOfText = asOf ? new Date(asOf).toUTCString() : ''

  return (
    <section>
      <h2>ECB euro area AAA spot time series</h2>
      <label>
        Maturity{' '}
        <select value={maturity} onChange={(event) => setMaturity(event.target.value)}>
          {MATURITIES.map((tenor) => (
            <option key={tenor} value={tenor}>
              {tenor}
            </option>
          ))}
        </select>
      </label>{' '}
      <label>
        From{' '}
        <input
          type="date"
          value={range.from}
          onChange={(event) => {
            if (event.target.value) setRange({ ...range, from: event.target.value })
          }}
        />
      </label>{' '}
      <label>
        To{' '}
        <input
          type="date"
          value={range.to}
          onChange={(event) => {
            if (event.target.value) setRange({ ...range, to: event.target.value })
          }}
        />
      </label>
      <AsOfControl asOf={asOf} onChange={changeAsOf} />
      {asOf && <p role="status">Showing the series as known on {asOfText}</p>}
      {result === undefined && <p>Loading…</p>}
      {result?.kind === 'ok' && result.series.data.points.length > 0 && (
        <SeriesChart points={result.series.data.points} />
      )}
      {result?.kind === 'ok' && result.series.data.points.length === 0 && (
        <p role="status">No values in this range.</p>
      )}
      {result?.kind === 'offline' && (
        <p role="alert">Backend offline: the YieldLens API is not reachable. Try again later.</p>
      )}
      {result?.kind === 'not-found' && !asOf && (
        <p role="status">No data known for this maturity.</p>
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
