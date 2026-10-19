import { cleanup, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import App from './App'

vi.mock('./curve/CurveView', () => ({
  default: () => <p>Curve view</p>,
}))

afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
})

describe('App', () => {
  it('shows the backend offline state when access is unreachable', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new TypeError('Failed to fetch')))

    render(<App />)

    expect(await screen.findByRole('alert')).toHaveTextContent('Backend offline')
  })

  it('shows the curve view when access is healthy', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: true }))

    render(<App />)

    expect(await screen.findByText('Curve view')).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'YieldLens' })).toBeInTheDocument()
  })
})
