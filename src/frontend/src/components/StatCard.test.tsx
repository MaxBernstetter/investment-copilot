import { act, cleanup, render, screen } from '../test/render'
import { afterEach, describe, expect, it } from 'vitest'
import { theme } from '../theme'
import StatCard from './StatCard'

type TextStyles = (t: unknown, p: { variant?: string }) => { root: object }

afterEach(() => {
  cleanup()
})

describe('StatCard', () => {
  it('shows label, value and hint', () => {
    render(<StatCard label="10Y yield" value={'2.600\u202F%'} hint="Value flagged" />)

    expect(screen.getByText('10Y yield')).toBeInTheDocument()
    expect(screen.getByText(/^2\.600/)).toBeInTheDocument()
    expect(screen.getByText('Value flagged')).toBeInTheDocument()
  })

  it('has no info button without help', () => {
    render(<StatCard label="10Y yield" value="2.600" />)

    expect(screen.queryByRole('button')).toBeNull()
  })

  it('has an About button with help', () => {
    render(<StatCard label="10Y yield" value="2.600" help="Spot rate for a 10-year maturity." />)

    expect(screen.getByRole('button', { name: 'About 10Y yield' })).toBeInTheDocument()
  })

  it('opens the help tooltip on keyboard focus', () => {
    render(<StatCard label="10Y yield" value="2.600" help="Spot rate for a 10-year maturity." />)

    act(() => screen.getByRole('button', { name: 'About 10Y yield' }).focus())

    expect(screen.getByRole('tooltip')).toHaveTextContent('Spot rate for a 10-year maturity.')
  })

  it('shows the badge next to the value', () => {
    render(<StatCard label="2Y–10Y spread" value={'\u221215.0 bp'} badge={<span>Inverted</span>} />)

    expect(screen.getByText('Inverted')).toBeInTheDocument()
    expect(screen.getByText('\u221215.0 bp')).toBeInTheDocument()
  })

  it('shows a skeleton in place of the value and hides hint and badge while loading', () => {
    const { container } = render(
      <StatCard label="2Y–10Y spread" value="+52.1 bp" hint="Input flagged: 10Y" badge={<span>Inverted</span>} loading />,
    )

    expect(screen.queryByText('+52.1 bp')).toBeNull()
    expect(screen.queryByText('Input flagged: 10Y')).toBeNull()
    expect(screen.queryByText('Inverted')).toBeNull()
    expect(container.querySelector('.mantine-Skeleton-root')).not.toBeNull()
  })

  it('marks the value for tabular numerals', () => {
    render(<StatCard label="Last" value={'2.600\u202F%'} />)

    const value = screen.getByText(/^2\.600/)
    expect(value).toHaveAttribute('data-variant', 'tabular')
    expect(value).toHaveStyle({ fontVariantNumeric: 'tabular-nums' })
  })

  it('maps the tabular variant to tabular-nums in the theme', () => {
    const styles = theme.components!.Text.styles as TextStyles

    expect(styles(theme, { variant: 'tabular' }).root).toEqual({ fontVariantNumeric: 'tabular-nums' })
    expect(styles(theme, {}).root).toEqual({})
  })
})
