import { afterEach, describe, expect, it } from 'vitest'
import userEvent from '@testing-library/user-event'
import { cleanup, render, screen, waitFor } from '../test/render'
import { METHODOLOGY_URL } from '../config'
import HowWeCheck from './HowWeCheck'

afterEach(cleanup)

describe('HowWeCheck', () => {
  it('renders four rules and opens the Jump panel on click', async () => {
    const user = userEvent.setup()
    render(<HowWeCheck />)

    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'How we check' }))
    expect(await screen.findByRole('dialog', { name: 'How we check' })).toBeInTheDocument()
    const controls = ['Range', 'Jump', 'Missing date', 'Missing maturity'].map((label) =>
      screen.getByRole('button', { name: label }),
    )
    expect(controls).toHaveLength(4)

    const jump = screen.getByRole('button', { name: 'Jump' })
    await user.click(jump)
    await waitFor(() => expect(jump).toHaveAttribute('aria-expanded', 'true'))
    const text = await screen.findByText(/more than 25 bp since the previous business day/)
    await waitFor(() => expect(text).toBeVisible())

    expect(screen.getByRole('link', { name: 'Read the full method' })).toHaveAttribute(
      'href',
      METHODOLOGY_URL,
    )
  })
})
