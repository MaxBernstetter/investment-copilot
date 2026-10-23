import { afterEach, describe, expect, it } from 'vitest'
import { cleanup, render, screen, within } from '../test/render'
import { AAA, ALL, PAR } from '../test/catalogue'
import OverlayNotes from './OverlayNotes'

describe('OverlayNotes', () => {
  afterEach(cleanup)

  it('shows no note for curves with the same convention, and one attribution per source', () => {
    render(<OverlayNotes curves={[AAA, ALL]} />)
    expect(screen.queryByRole('note')).toBeNull()
    const list = screen.getByRole('list')
    expect(within(list).getAllByRole('listitem')).toHaveLength(1)
    expect(
      within(list).getByText('Source: ECB statistics (ECB euro area AAA spot, ECB euro area all-issuer spot)'),
    ).toBeVisible()
  })

  it('shows the comparability note for mixed rate types and compounding', () => {
    render(<OverlayNotes curves={[AAA, PAR]} />)
    expect(screen.getByRole('note')).toHaveTextContent(
      'These curves are not directly comparable: rate types differ (spot, par) and compounding differs (continuous, semi-annual). A gap between lines can come from the convention, not from the market.',
    )
  })

  it('lists one attribution line per curve when the sources differ', () => {
    render(<OverlayNotes curves={[AAA, PAR]} />)
    const items = within(screen.getByRole('list')).getAllByRole('listitem')
    expect(items.map((item) => item.textContent)).toEqual([
      'Source: ECB statistics (ECB euro area AAA spot)',
      'Source: U.S. Department of the Treasury (US Treasury par)',
    ])
  })
})
