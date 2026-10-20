import { cleanup, fireEvent, render, screen } from '../test/render'
import { afterEach, describe, expect, it, vi } from 'vitest'
import AsOfStatus from './AsOfStatus'

afterEach(cleanup)

describe('AsOfStatus', () => {
  it('reads Live when no knowledge time is set', () => {
    render(<AsOfStatus asOf={undefined} onChange={vi.fn()} />)

    expect(screen.getByRole('status')).toHaveTextContent('Live')
    expect(screen.getByRole('button', { name: 'Live' })).toBeInTheDocument()
  })

  it('reads the past knowledge time in UTC', () => {
    render(<AsOfStatus asOf="2026-10-19T18:49:25Z" onChange={vi.fn()} />)

    expect(screen.getByRole('button', { name: 'As of 19 Oct 2026, 18:49:25 UTC' })).toBeInTheDocument()
  })

  it('clears the knowledge time with Now', () => {
    const onChange = vi.fn()
    render(<AsOfStatus asOf="2026-10-19T18:49:25Z" onChange={onChange} />)

    fireEvent.click(screen.getByRole('button', { name: 'As of 19 Oct 2026, 18:49:25 UTC' }))
    fireEvent.click(screen.getByRole('button', { name: 'Now' }))

    expect(onChange).toHaveBeenCalledWith(undefined)
  })

  it('reports a chosen time in UTC-based ISO form', () => {
    const onChange = vi.fn()
    render(<AsOfStatus asOf={undefined} onChange={onChange} />)

    fireEvent.click(screen.getByRole('button', { name: 'Live' }))
    fireEvent.change(screen.getByLabelText(/Known as of/), {
      target: { value: '2026-10-19T18:49:25' },
    })

    expect(onChange).toHaveBeenCalledWith(new Date('2026-10-19T18:49:25').toISOString())
  })
})
