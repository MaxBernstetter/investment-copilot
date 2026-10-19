import { useEffect, useMemo, useState } from 'react'
import { readAsOf, writeAsOf } from '../asOf'
import AsOfControl from './AsOfControl'
import CurveChart from './CurveChart'
import { missingMaturities, type LabelledCurve } from './curveData'
import { fetchCurve, type CurveResult } from './fetchCurve'

const MAX_OVERLAYS = 5

export default function CurveView() {
  const [validDate, setValidDate] = useState<string | undefined>(undefined)
  const [asOf, setAsOf] = useState<string | undefined>(() => readAsOf(window.location.search))
  const [result, setResult] = useState<CurveResult | undefined>(undefined)
  const [overlayDates, setOverlayDates] = useState<string[]>([])
  const [overlayCurves, setOverlayCurves] = useState<LabelledCurve[]>([])

  useEffect(() => {
    let active = true
    fetchCurve({ validDate, asOf }).then((next) => {
      if (active) setResult(next)
    })
    return () => {
      active = false
    }
  }, [validDate, asOf])

  useEffect(() => {
    let active = true
    Promise.all(overlayDates.map((date) => fetchCurve({ validDate: date, asOf }))).then(
      (results) => {
        if (!active) return
        setOverlayCurves(
          results.flatMap((next, i) =>
            next.kind === 'ok' ? [{ label: overlayDates[i], points: next.curve.data.points }] : [],
          ),
        )
      },
    )
    return () => {
      active = false
    }
  }, [overlayDates, asOf])

  const changeAsOf = (next: string | undefined) => {
    setAsOf(next)
    writeAsOf(next)
  }

  const returnedDate = result?.kind === 'ok' ? result.curve.data.valid_date : ''
  const shownDate = validDate ?? returnedDate
  const canAddOverlay =
    shownDate !== '' && !overlayDates.includes(shownDate) && overlayDates.length < MAX_OVERLAYS

  const curves = useMemo<LabelledCurve[]>(() => {
    if (result?.kind !== 'ok') return []
    const current = { label: result.curve.data.valid_date, points: result.curve.data.points }
    const overlays = overlayCurves.filter(
      (curve) => overlayDates.includes(curve.label) && curve.label !== current.label,
    )
    return [current, ...overlays]
  }, [result, overlayCurves, overlayDates])

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
          <div>
            <button
              type="button"
              disabled={!canAddOverlay}
              onClick={() => setOverlayDates((dates) => [...dates, shownDate])}
            >
              Add to overlay
            </button>
          </div>
          {overlayDates.length > 0 && (
            <ul aria-label="Overlaid valid dates">
              {overlayDates.map((date) => (
                <li key={date}>
                  {date}{' '}
                  <button
                    type="button"
                    aria-label={`Remove ${date}`}
                    onClick={() => setOverlayDates((dates) => dates.filter((d) => d !== date))}
                  >
                    ×
                  </button>
                </li>
              ))}
            </ul>
          )}
          <CurveChart curves={curves} />
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
