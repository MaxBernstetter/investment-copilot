import { cleanup, fireEvent, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'
import App from './App'
import { localInputToUtc } from './asOf'
import CurveView from './curve/CurveView'
import { formatUtc } from './format'
import { METHODOLOGY_URL } from './config'
import { render } from './test/render'

// Each view shows the knowledge time it received, so the tests can check what every tab sees.
vi.mock('./curve/CurveView', () => ({
  default: vi.fn(({ asOf }: { asOf?: string }) => (
    <>
      <p>Curve view</p>
      <p>{`Curve knows ${asOf ?? 'live'}`}</p>
    </>
  )),
}))

vi.mock('./series/SeriesView', () => ({
  default: ({ asOf }: { asOf?: string }) => (
    <>
      <p>Time series view</p>
      <p>{`Series knows ${asOf ?? 'live'}`}</p>
    </>
  ),
}))

vi.mock('./changes/ChangesView', () => ({
  default: ({ asOf }: { asOf?: string }) => (
    <>
      <p>Changes view</p>
      <p>{`Changes know ${asOf ?? 'live'}`}</p>
    </>
  ),
}))

/** The Simulated badge in the header (the curve control shows the same word as a radio label). */
const simulatedBadges = () =>
  Array.from(document.querySelectorAll('.mantine-Badge-label')).filter((el) => el.textContent === 'Simulated')

/** The navbar on small screens: the second "Views" navigation, after the header tabs. */
const navbarOf = () => screen.getAllByRole('navigation', { name: 'Views' }).at(-1)!

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

    expect(await screen.findByRole('alert')).toHaveTextContent('Backend offline')
    expect(screen.getByRole('alert')).toHaveTextContent('The YieldLens API is not reachable. Try again in a moment.')
    expect(screen.getByRole('heading', { level: 1, name: 'Service unavailable' })).toBeInTheDocument()
    expect(screen.getAllByRole('heading', { level: 1 })).toHaveLength(1)
    expect(screen.getByRole('button', { name: 'Try again' })).toBeInTheDocument()
    expect(screen.getByText('YieldLens')).toBeInTheDocument()
    expect(screen.getByRole('banner')).toBeInTheDocument()
    expect(screen.getByRole('contentinfo')).toBeInTheDocument()
  })

  it('shows one h1 while the health check runs', async () => {
    vi.stubGlobal('fetch', vi.fn(() => new Promise(() => {})))

    render(<App />)

    expect(screen.getByRole('heading', { level: 1, name: 'Connecting' })).toBeInTheDocument()
    expect(screen.getAllByRole('heading', { level: 1 })).toHaveLength(1)
    expect(screen.getByText('Loading…')).toBeInTheDocument()
  })

  it('exposes the page landmarks and no YieldLens heading', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: true }))

    render(<App />)
    expect(await screen.findByText('Curve view')).toBeInTheDocument()

    expect(screen.getByRole('banner')).toBeInTheDocument()
    expect(screen.getAllByRole('navigation', { name: 'Views' })).toHaveLength(2)
    expect(screen.getByRole('main')).toBeInTheDocument()
    expect(screen.getByRole('contentinfo')).toBeInTheDocument()
    expect(screen.queryByRole('heading', { name: 'YieldLens' })).not.toBeInTheDocument()
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
    expect(within(footer).getByRole('link', { name: 'ECB copyright notice' })).toHaveAttribute(
      'href',
      'https://www.ecb.europa.eu/services/using-our-site/disclaimer/html/index.en.html',
    )
    expect(within(footer).getByRole('link', { name: 'ECB statistics' })).toHaveAttribute('data-underline', 'always')
    expect(within(footer).getByRole('link', { name: 'ECB copyright notice' })).toHaveAttribute(
      'data-underline',
      'always',
    )
    expect(within(footer).getByText('v0.1.0 · dev')).toBeInTheDocument()
  })

  it('shows scenario data in the footer instead of the ECB source for the simulated curve', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: true }))

    render(<App />)
    expect(await screen.findByText('Curve view')).toBeInTheDocument()
    fireEvent.click(screen.getByRole('radio', { name: 'Simulated' }))

    const footer = screen.getByRole('contentinfo')
    expect(within(footer).getByText('Scenario data, not published by the ECB.')).toBeInTheDocument()
    expect(within(footer).queryByRole('link', { name: 'ECB statistics' })).not.toBeInTheDocument()
  })

  it('opens the navbar with the burger and closes it after a choice', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: true }))

    render(<App />)
    expect(await screen.findByText('Curve view')).toBeInTheDocument()
    const burger = screen.getByRole('button', { name: 'Toggle navigation' })
    expect(burger).toHaveAttribute('aria-expanded', 'false')
    expect(within(navbarOf()).queryByRole('button', { name: 'Changes' })).not.toBeInTheDocument()

    fireEvent.click(burger)

    expect(burger).toHaveAttribute('aria-expanded', 'true')
    expect(within(navbarOf()).getByRole('button', { name: 'Curve' })).toHaveAttribute('aria-current', 'page')
    expect(within(navbarOf()).getByRole('button', { name: 'Time series' })).not.toHaveAttribute('aria-current')
    fireEvent.click(within(navbarOf()).getByRole('button', { name: 'Changes' }))

    expect(screen.getByText('Changes view')).toBeVisible()
    expect(burger).toHaveAttribute('aria-expanded', 'false')
    expect(within(navbarOf()).queryByRole('button', { name: 'Changes' })).not.toBeInTheDocument()
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

  it('shows Live in the header by default and the past time when one is set', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: true }))

    render(<App />)
    expect(await screen.findByText('Curve view')).toBeInTheDocument()
    expect(screen.getByRole('status')).toHaveTextContent('Live')
    expect(screen.getByRole('button', { name: 'Live' })).toHaveAttribute('data-variant', 'default')

    cleanup()
    window.history.replaceState(null, '', '/?as_of=2026-10-19T18:49:25Z')
    render(<App />)
    expect(await screen.findByText('Curve view')).toBeInTheDocument()
    expect(screen.getByRole('status')).toHaveTextContent('As of 19 Oct 2026, 18:49:25 UTC')
    expect(screen.getByRole('button', { name: 'As of 19 Oct 2026, 18:49:25 UTC' })).toHaveAttribute('data-variant', 'filled')
    expect(screen.getByText('Curve knows 2026-10-19T18:49:25Z')).toBeInTheDocument()
  })

  it('opens the known-as-of popover with Enter and closes it with Esc', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: true }))
    const user = userEvent.setup()

    render(<App />)
    expect(await screen.findByText('Curve view')).toBeInTheDocument()
    const status = screen.getByRole('button', { name: 'Live' })
    status.focus()

    await user.keyboard('{Enter}')
    expect(screen.getByLabelText(/Known as of/)).toBeVisible()
    expect(screen.getByRole('button', { name: 'Now' })).toBeVisible()
    expect(screen.getByText(/Choose Now to see the latest knowledge/)).toBeVisible()

    await user.keyboard('{Escape}')
    expect(screen.queryByLabelText(/Known as of/)).not.toBeInTheDocument()
    expect(status).toHaveFocus()

    await user.keyboard(' ')
    expect(screen.getByLabelText(/Known as of/)).toBeVisible()
  })

  it('shares a change of the knowledge time with every view', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: true }))
    const chosen = '2026-10-01T12:00:00'
    const asOf = localInputToUtc(chosen)

    render(<App />)
    expect(await screen.findByText('Curve view')).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Live' }))
    fireEvent.change(screen.getByLabelText(/Known as of/), { target: { value: chosen } })

    expect(screen.getByText(`Curve knows ${asOf}`)).toBeInTheDocument()
    expect(screen.getByRole('status')).toHaveTextContent(`As of ${formatUtc(asOf)}`)
    expect(new URLSearchParams(window.location.search).get('as_of')).toBe(asOf)

    fireEvent.click(screen.getByRole('tab', { name: 'Time series' }))
    expect(screen.getByText(`Series knows ${asOf}`)).toBeInTheDocument()

    fireEvent.click(screen.getByRole('tab', { name: 'Changes' }))
    expect(screen.getByText(`Changes know ${asOf}`)).toBeInTheDocument()

    fireEvent.click(screen.getByRole('button', { name: 'Now' }))

    expect(screen.getByText('Changes know live')).toBeInTheDocument()
    expect(screen.getByRole('status')).toHaveTextContent('Live')
    expect(new URLSearchParams(window.location.search).has('as_of')).toBe(false)

    fireEvent.click(screen.getByRole('tab', { name: 'Curve' }))
    expect(screen.getByText('Curve knows live')).toBeInTheDocument()
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
