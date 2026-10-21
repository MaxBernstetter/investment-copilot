import { afterEach, describe, expect, it } from 'vitest'
import { cleanup, render, screen } from '../test/render'
import { METHODOLOGY_URL } from '../config'
import UncheckedNote from './UncheckedNote'

afterEach(cleanup)

describe('UncheckedNote', () => {
  it('explains unchecked and links to the method', () => {
    render(<UncheckedNote />)

    expect(screen.getByText('Unchecked means the quality checks have not run on the value yet.')).toBeInTheDocument()
    const link = screen.getByRole('link', { name: 'How we check this' })
    expect(link).toHaveAttribute('href', METHODOLOGY_URL)
    expect(link).toHaveAttribute('target', '_blank')
    expect(link).toHaveAttribute('data-underline', 'always')
  })
})
