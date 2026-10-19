import { cleanup, fireEvent, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import App from './App'
import CurveView from './curve/CurveView'
import { render } from './test/render'

vi.mock('./curve/CurveView', () => ({
  default: vi.fn(() => <p>Curve view</p>),
}))

vi.mock('./series/SeriesView', () => ({
  default: () => <p>Time series view</p>,
}))

vi.mock('./changes/ChangesView', () => ({
  default: () => <p>Changes view</p>,
}))

afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
  vi.clearAllMocks()
  window.history.replaceState(null, '', '/')
})

describe('App', () => {
  it('shows the backend offline state when access is unreachable', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new TypeError('Failed to fetch')))

    render(<App />)

    expect(await screen.findByRole('alert')).toHaveTextContent(
      'Backend offline: the YieldLens API is not reachable. Try again later.',
    )
  })

  it('shows the curve view when access is healthy', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: true }))

    render(<App />)

    expect(await screen.findByText('Curve view')).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'YieldLens' })).toBeInTheDocument()
  })

  it('switches between the curve and time series views', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: true }))

    render(<App />)
    expect(await screen.findByText('Curve view')).toBeInTheDocument()

    fireEvent.click(screen.getByRole('tab', { name: 'Time series' }))
    expect(screen.getByText('Time series view')).toBeVisible()
    expect(screen.getByText('Curve view')).not.toBeVisible()

    fireEvent.click(screen.getByRole('tab', { name: 'Curve' }))
    expect(screen.getByText('Curve view')).toBeVisible()
    expect(screen.getByText('Time series view')).not.toBeVisible()
  })

  it('switches to the changes view', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: true }))

    render(<App />)
    expect(await screen.findByText('Curve view')).toBeInTheDocument()

    fireEvent.click(screen.getByRole('tab', { name: 'Changes' }))
    expect(screen.getByText('Changes view')).toBeVisible()
    expect(screen.getByText('Curve view')).not.toBeVisible()
  })

  it('keeps the curve view mounted when switching tabs', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: true }))

    render(<App />)
    expect(await screen.findByText('Curve view')).toBeInTheDocument()

    fireEvent.click(screen.getByRole('tab', { name: 'Time series' }))

    expect(screen.getByText('Curve view')).toBeInTheDocument()
    expect(screen.getByText('Curve view')).not.toBeVisible()
  })

  it('shows the simulated notice only for the simulated curve', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: true }))

    render(<App />)
    expect(await screen.findByText('Curve view')).toBeInTheDocument()
    expect(screen.queryByRole('note')).not.toBeInTheDocument()
    expect(screen.getAllByText('Simulated')).toHaveLength(1)

    fireEvent.click(screen.getByRole('radio', { name: 'Simulated' }))

    expect(screen.getByRole('note')).toHaveTextContent(
      'Simulated data from a scenario, not real source data.',
    )
    expect(screen.getAllByText('Simulated')).toHaveLength(2)

    fireEvent.click(screen.getByRole('radio', { name: 'Real' }))

    expect(screen.queryByRole('note')).not.toBeInTheDocument()
    expect(screen.getAllByText('Simulated')).toHaveLength(1)
  })

  it('passes the chosen curve to the curve view', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: true }))
    window.history.replaceState(null, '', '/?curve=ecb-aaa-spot-sim')

    render(<App />)
    expect(await screen.findByText('Curve view')).toBeInTheDocument()

    expect(vi.mocked(CurveView).mock.lastCall?.[0]).toMatchObject({ curveId: 'ecb-aaa-spot-sim' })
    expect(new URLSearchParams(window.location.search).get('curve')).toBe('ecb-aaa-spot-sim')
  })
})
