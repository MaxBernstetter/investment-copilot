import { afterEach, describe, expect, it } from 'vitest'
import { cleanup, render, screen, within } from '../test/render'
import { AAA, ALL, PAR } from '../test/catalogue'
import OverlayNotes from './OverlayNotes'
import type { LabelledCurve } from './curveData'

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

  it('shows one missing-value line per curve that lacks tenors other curves publish, above the attribution', () => {
    const value = (months: number) => ({
      maturity: `${months}M`,
      months,
      value: 2,
      version_id: 1,
      origin: 'published' as const,
      quality: null,
    })
    const drawn: LabelledCurve[] = [
      {
        key: 'a',
        label: 'AAA · 2026-10-16',
        points: [value(3), value(1.5), value(240)] as LabelledCurve['points'],
        slot: 0,
      },
      { key: 'b', label: 'PAR · 2026-10-16', points: [value(3)] as LabelledCurve['points'], slot: 1 },
    ]
    render(<OverlayNotes curves={[AAA, PAR]} drawn={drawn} />)
    expect(screen.getByText('No value on PAR · 2026-10-16: 1.5M, 20Y.')).toBeVisible()
    expect(screen.getAllByText(/^No value on /)).toHaveLength(1)
  })

  it('counts instead of listing when more than eight tenors are missing', () => {
    const value = (months: number) => ({
      maturity: `${months}M`,
      months,
      value: 2,
      version_id: 1,
      origin: 'published' as const,
      quality: null,
    })
    const many = Array.from({ length: 10 }, (_, i) => value(i + 1))
    const drawn = [
      { key: 'a', label: 'AAA · 2026-10-16', points: many, slot: 0 },
      { key: 'b', label: 'PAR · 2026-10-16', points: [value(3)], slot: 1 },
    ] as LabelledCurve[]
    render(<OverlayNotes curves={[AAA, PAR]} drawn={drawn} />)
    expect(screen.getByText('No value on PAR · 2026-10-16 for 9 maturities.')).toBeVisible()
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
