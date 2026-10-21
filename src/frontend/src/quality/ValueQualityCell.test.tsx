import { afterEach, describe, expect, it } from 'vitest'
import userEvent from '@testing-library/user-event'
import { cleanup, render, screen } from '../test/render'
import { METHODOLOGY_URL } from '../config'
import ValueQualityCell from './ValueQualityCell'
import type { ValueQuality } from './qualityData'

afterEach(cleanup)

const rangeFlag = {
  rule: 'range',
  severity: 'warn' as const,
  explanation: 'Range at 10Y is outside the plausible band.',
  evidence: '12.000 % on 2026-10-16',
}
const jumpFlag = {
  rule: 'jump',
  severity: 'info' as const,
  explanation: 'Moved more than 25 bp.',
  evidence: '2.800 % on 2026-10-16 after 2.700 % on 2026-10-15 (+10.0 bp)',
}

function renderCell(quality: ValueQuality | null) {
  return render(
    <div data-testid="cell">
      <ValueQualityCell quality={quality} maturity="10Y" />
    </div>,
  )
}

describe('ValueQualityCell', () => {
  it('renders nothing for a missing value', () => {
    renderCell(null)
    expect(screen.getByTestId('cell')).toBeEmptyDOMElement()
  })

  it('passed reads Passed for screen readers only', () => {
    renderCell({ status: 'passed', flags: [] })
    expect(screen.getByText('Passed')).toBeInTheDocument()
    expect(screen.queryByRole('button')).toBeNull()
  })

  it('warn flags become badges, warnings first', () => {
    renderCell({ status: 'warn', flags: [jumpFlag, rangeFlag] })
    const names = screen.getAllByRole('button').map((button) => button.getAttribute('aria-label'))
    expect(names).toEqual(['Range · warn, 10Y', 'Jump · info, 10Y'])
  })

  it('a flag badge opens its explanation and evidence', async () => {
    const user = userEvent.setup()
    renderCell({ status: 'warn', flags: [rangeFlag] })

    await user.click(screen.getByRole('button', { name: 'Range · warn, 10Y' }))
    expect(await screen.findByText('Range at 10Y')).toBeVisible()
    expect(screen.getByText(rangeFlag.explanation)).toBeVisible()
    expect(screen.getByText(rangeFlag.evidence)).toBeVisible()
    expect(screen.getByRole('link', { name: 'How we check this' })).toHaveAttribute('href', METHODOLOGY_URL)
  })

  it('info or warn without flags shows a static status badge', () => {
    renderCell({ status: 'warn', flags: [] })
    expect(screen.getByText('Warn')).toBeInTheDocument()
    expect(screen.queryByRole('button')).toBeNull()
  })

  it('unchecked shows a static Unchecked badge that is not focusable', () => {
    renderCell({ status: 'unchecked', flags: [] })
    const badge = screen.getByText('Unchecked')
    expect(screen.queryByRole('button')).toBeNull()
    expect(badge.closest('[tabindex]')).toBeNull()
  })
})
