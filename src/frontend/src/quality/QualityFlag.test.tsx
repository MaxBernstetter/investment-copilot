import { afterEach, describe, expect, it } from 'vitest'
import userEvent from '@testing-library/user-event'
import { cleanup, render, screen, waitFor } from '../test/render'
import { METHODOLOGY_URL } from '../config'
import type { QualityFinding } from './qualityData'
import QualityFlag from './QualityFlag'

const finding: QualityFinding = {
  rule: 'range',
  severity: 'warn',
  maturity: '10Y',
  explanation: 'Yields outside the plausible range are flagged.',
  evidence: 'Value 12.00 % is outside the range.',
}

afterEach(cleanup)

describe('QualityFlag', () => {
  it('Enter opens and focuses How we check this', async () => {
    const user = userEvent.setup()
    render(<QualityFlag finding={finding} />)

    const badge = screen.getByRole('button', { name: 'Range · warn, 10Y' })
    badge.focus()
    await user.keyboard('{Enter}')

    const link = await screen.findByRole('link', { name: 'How we check this' })
    await waitFor(() => expect(link).toHaveFocus())
    await waitFor(() => expect(screen.getByText('Range at 10Y')).toBeVisible())
    await waitFor(() => expect(screen.getByText(finding.explanation)).toBeVisible())
    await waitFor(() => expect(screen.getByText(finding.evidence)).toBeVisible())
  })

  it('shows only the rule label in the popover when there is no maturity', async () => {
    const user = userEvent.setup()
    render(<QualityFlag finding={{ ...finding, maturity: null }} />)

    await user.click(screen.getByRole('button', { name: 'Range · warn' }))
    await screen.findByRole('link', { name: 'How we check this' })
    await waitFor(() => expect(screen.getByText('Range')).toBeVisible())
    expect(screen.queryByText('Range at 10Y')).not.toBeInTheDocument()
  })

  it('Escape closes and returns focus to the badge', async () => {
    const user = userEvent.setup()
    render(<QualityFlag finding={finding} />)

    const badge = screen.getByRole('button', { name: 'Range · warn, 10Y' })
    badge.focus()
    await user.keyboard('{Enter}')
    await screen.findByRole('link', { name: 'How we check this' })

    await user.keyboard('{Escape}')
    await waitFor(() =>
      expect(screen.queryByRole('link', { name: 'How we check this' })).not.toBeInTheDocument(),
    )
    expect(badge).toHaveFocus()
  })

  it('link points to METHODOLOGY_URL with target _blank', async () => {
    const user = userEvent.setup()
    render(<QualityFlag finding={finding} />)

    await user.click(screen.getByRole('button', { name: 'Range · warn, 10Y' }))
    const link = await screen.findByRole('link', { name: 'How we check this' })
    expect(link).toHaveAttribute('href', METHODOLOGY_URL)
    expect(link).toHaveAttribute('target', '_blank')
  })

  it('shows an unknown rule by its raw name', () => {
    render(<QualityFlag finding={{ rule: 'curvature', severity: 'info', maturity: '10Y', explanation: '', evidence: '' }} />)
    expect(screen.getByRole('button', { name: 'curvature · info, 10Y' })).toBeInTheDocument()
  })

  it('aria-label names the maturity', () => {
    render(<QualityFlag finding={finding} />)
    expect(screen.getByRole('button', { name: 'Range · warn, 10Y' })).toBeInTheDocument()
  })
})
