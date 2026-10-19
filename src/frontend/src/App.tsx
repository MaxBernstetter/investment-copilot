import { useEffect, useState } from 'react'
import { isBackendOnline } from './backend'
import CurveView from './curve/CurveView'
import SeriesView from './series/SeriesView'

type BackendState = 'checking' | 'online' | 'offline'
type View = 'curve' | 'series'

export default function App() {
  const [state, setState] = useState<BackendState>('checking')
  const [view, setView] = useState<View>('curve')

  useEffect(() => {
    let active = true
    isBackendOnline().then((online) => {
      if (active) setState(online ? 'online' : 'offline')
    })
    return () => {
      active = false
    }
  }, [])

  return (
    <main>
      <h1>YieldLens</h1>
      {state === 'checking' && <p>Loading…</p>}
      {state === 'offline' && (
        <p role="alert">Backend offline: the YieldLens API is not reachable. Try again later.</p>
      )}
      {state === 'online' && (
        <>
          <nav>
            <button type="button" aria-pressed={view === 'curve'} onClick={() => setView('curve')}>
              Curve
            </button>{' '}
            <button
              type="button"
              aria-pressed={view === 'series'}
              onClick={() => setView('series')}
            >
              Time series
            </button>
          </nav>
          {view === 'curve' ? <CurveView /> : <SeriesView />}
        </>
      )}
    </main>
  )
}
