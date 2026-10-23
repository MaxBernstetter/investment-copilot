import { cleanup, render, screen, within } from '../test/render'
import { afterEach, describe, expect, it } from 'vitest'
import AppFooter from './AppFooter'
import { AAA, PAR, SIM } from '../test/catalogue'

const TERMS = 'https://www.ecb.europa.eu/services/using-our-site/disclaimer/html/index.en.html'

describe('AppFooter', () => {
  afterEach(cleanup)

  it('names the ECB source, the curve and the reuse terms for a published ECB curve', () => {
    render(<AppFooter curve={AAA} />)

    const footer = screen.getByRole('contentinfo')
    expect(footer).toHaveTextContent(
      'Source: ECB statistics, ECB euro area AAA spot. Reuse with attribution, see the ECB copyright notice.',
    )
    expect(within(footer).getByRole('link', { name: 'ECB copyright notice' })).toHaveAttribute('href', TERMS)
    expect(within(footer).getByRole('link', { name: 'ECB copyright notice' })).toHaveAttribute('data-underline', 'always')
  })

  it('names the attribution and curve without a terms link for a published curve without terms', () => {
    render(<AppFooter curve={PAR} />)

    const footer = screen.getByRole('contentinfo')
    expect(footer).toHaveTextContent('Source: U.S. Department of the Treasury, US Treasury par.')
    expect(within(footer).queryByRole('link', { name: 'ECB copyright notice' })).not.toBeInTheDocument()
    expect(within(footer).getByRole('link', { name: 'Methodology' })).toBeInTheDocument()
  })

  it('says the simulated curve is scenario data, not published by its publisher', () => {
    render(<AppFooter curve={SIM} />)

    expect(screen.getByRole('contentinfo')).toHaveTextContent(
      'Simulated scenario based on ECB statistics. Scenario data, not published by the ECB.',
    )
  })

  it('keeps the links and version without a curve, with no attribution text', () => {
    render(<AppFooter />)

    const footer = screen.getByRole('contentinfo')
    expect(footer).not.toHaveTextContent('Source:')
    expect(footer).not.toHaveTextContent('Reuse with attribution')
    expect(within(footer).getByRole('link', { name: 'API docs' })).toBeInTheDocument()
    expect(within(footer).getByRole('link', { name: 'Methodology' })).toBeInTheDocument()
    expect(within(footer).getByRole('link', { name: 'GitHub' })).toBeInTheDocument()
    expect(within(footer).getByText('v0.1.0 · dev')).toBeInTheDocument()
  })
})
