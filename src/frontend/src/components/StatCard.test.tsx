import { render, screen } from '../test/render'
import { describe, expect, it } from 'vitest'
import { theme } from '../theme'
import StatCard from './StatCard'

type TextStyles = (t: unknown, p: { variant?: string }) => { root: object }

describe('StatCard', () => {
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
