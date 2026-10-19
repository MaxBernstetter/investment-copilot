import { useEffect, useState } from 'react'
import { isBackendOnline } from './backend'
import CurveView from './curve/CurveView'

type BackendState = 'checking' | 'online' | 'offline'

export default function App() {
  const [state, setState] = useState<BackendState>('checking')

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
      {state === 'online' && <CurveView />}
    </main>
  )
}
