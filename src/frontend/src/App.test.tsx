import { cleanup, fireEvent, screen, within } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import App from './App'
import CurveView from './curve/CurveView'
import { METHODOLOGY_URL } from './config'
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

/** The Simulated badge in the header (the curve control shows the same word as a radio label). */
const simulatedBadges = () =>
  Array.from(document.querySelectorAll('.mantine-Badge-label')).filter((el) => el.textContent === 'Simulated')

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
    expect(screen.getByText('YieldLens')).toBeInTheDocument()
  })

  it('retries the health check from the offline alert', async () => {
    const fetchMock = vi
      .fn()
      .mockRejectedValueOnce(new TypeError('Failed to fetch'))
      .mockResolvedValue({ ok: true })
    vi.stubGlobal('fetch', fetchMock)

    render(<App />)
    fireEvent.click(await screen.findByRole('button', { name: 'Try again' }))

    expect(await screen.findByText('Curve view')).toBeInTheDocument()
    expect(fetchMock).toHaveBeenCalledTimes(2)
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
    expect(simulatedBadges()).toHaveLength(0)

    fireEvent.click(screen.getByRole('radio', { name: 'Simulated' }))

    expect(screen.getByRole('note')).toHaveTextContent('Simulated scenario data, not an ECB publication.')
    expect(simulatedBadges()).toHaveLength(1)

    fireEvent.click(screen.getByRole('radio', { name: 'Real' }))

    expect(screen.queryByRole('note')).not.toBeInTheDocument()
    expect(simulatedBadges()).toHaveLength(0)
  })

  it('shows the source, the links and the version in the footer', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: true }))

    render(<App />)
    expect(await screen.findByText('Curve view')).toBeInTheDocument()

    const footer = screen.getByRole('contentinfo')
    expect(within(footer).getByRole('link', { name: 'ECB statistics' })).toHaveAttribute(
      'href',
      'https://data.ecb.europa.eu/',
    )
    expect(within(footer).getByRole('link', { name: 'API docs' })).toHaveAttribute(
      'href',
      'http://localhost:8000/docs',
    )
    expect(within(footer).getByRole('link', { name: 'Methodology' })).toHaveAttribute(
      'href',
      METHODOLOGY_URL,
    )
    expect(within(footer).getByRole('link', { name: 'GitHub' })).toHaveAttribute(
      'href',
      'https://github.com/MaxBernstetter/yield-lens',
    )
    expect(within(footer).getByText('v0.1.0 · dev')).toBeInTheDocument()
  })

  it('opens the navbar with the burger and closes it after a choice', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: true }))

    render(<App />)
    expect(await screen.findByText('Curve view')).toBeInTheDocument()
    const nav = screen.getByRole('navigation')
    const burger = screen.getByRole('button', { name: 'Toggle navigation' })
    expect(burger).toHaveAttribute('aria-expanded', 'false')
    expect(within(nav).queryByRole('button', { name: 'Changes' })).not.toBeInTheDocument()

    fireEvent.click(burger)

    expect(burger).toHaveAttribute('aria-expanded', 'true')
    fireEvent.click(within(nav).getByRole('button', { name: 'Changes' }))

    expect(screen.getByText('Changes view')).toBeVisible()
    expect(burger).toHaveAttribute('aria-expanded', 'false')
    expect(within(nav).queryByRole('button', { name: 'Changes' })).not.toBeInTheDocument()
  })

  it('switches the colour scheme with the toggle', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: true }))

    render(<App />)
    expect(await screen.findByText('Curve view')).toBeInTheDocument()
    const toggle = screen.getByRole('button', { name: 'Toggle colour scheme' })

    fireEvent.click(toggle)
    expect(document.documentElement).toHaveAttribute('data-mantine-color-scheme', 'dark')

    fireEvent.click(toggle)
    expect(document.documentElement).toHaveAttribute('data-mantine-color-scheme', 'light')
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
