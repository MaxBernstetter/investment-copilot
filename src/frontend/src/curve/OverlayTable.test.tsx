import { afterEach, describe, expect, it } from 'vitest'
import { cleanup, render, screen, within } from '../test/render'
import type { CurvePoint, LabelledCurve } from './curveData'
import OverlayTable from './OverlayTable'

const quality = { status: 'passed' as const, flags: [] }
const point = (months: number, value: number | null): CurvePoint => ({
  maturity: `${months}M`,
  months,
  value,
  version_id: value === null ? null : 1,
  origin: 'published',
  quality: value === null ? null : quality,
})

const curves: LabelledCurve[] = [
  { key: 'a|2026-10-15', label: 'ECB AAA · 2026-10-15', points: [point(3, 2.1), point(1.5, 2.0)], slot: 0 },
  { key: 'b|2026-10-16', label: 'US par · 2026-10-16', points: [point(3, 2.4), point(1.5, null)], slot: 1 },
]

describe('OverlayTable', () => {
  afterEach(cleanup)

  it('has a caption naming the overlay and one row header per curve·date entry, in legend order', () => {
    render(<OverlayTable curves={curves} />)
    expect(screen.getByRole('table', { name: 'Overlaid curves: ECB AAA · 2026-10-15, US par · 2026-10-16' })).toBeVisible()
    const rows = screen.getAllByRole('row').filter((row) => row.closest('tbody') !== null)
    expect(rows.map((row) => within(row).getByRole('rowheader').textContent)).toEqual([
      'ECB AAA · 2026-10-15',
      'US par · 2026-10-16',
    ])
  })

  it('has a column header per tenor, with decimal tenors labelled', () => {
    render(<OverlayTable curves={curves} />)
    const headers = screen.getAllByRole('columnheader').map((header) => header.textContent)
    expect(headers).toEqual(['Curve · date', '1.5M', '3M'])
  })

  it('shows a missing tenor as an empty cell with a no-value text, not as zero', () => {
    render(<OverlayTable curves={curves} />)
    const usRow = screen.getAllByRole('row').filter((row) => row.closest('tbody') !== null)[1]
    const cells = within(usRow).getAllByRole('cell')
    expect(cells[0]).toHaveTextContent('No value')
    expect(cells[0].textContent).not.toContain('0.000')
    expect(cells[1]).toHaveTextContent('2.400')
  })
})
