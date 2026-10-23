import { describe, expect, it } from 'vitest'
import { gapNotes, sourceOf, validDateHelp } from './sources'
import { AAA, PAR, SIM } from '../test/catalogue'

describe('sourceOf', () => {
  it('knows the ECB publisher and terms', () => {
    expect(sourceOf(AAA)).toEqual({
      publisher: 'the ECB',
      termsUrl: 'https://www.ecb.europa.eu/services/using-our-site/disclaimer/html/index.en.html',
    })
  })

  it('knows the US Treasury publisher without terms', () => {
    expect(sourceOf(PAR)).toEqual({ publisher: 'U.S. Department of the Treasury' })
  })

  it('gives a neutral publisher for an unknown source', () => {
    expect(sourceOf({ ...PAR, sourceId: 'unknown' })).toEqual({ publisher: 'the source' })
  })
})

describe('validDateHelp', () => {
  it('explains the valid date per curve', () => {
    expect(validDateHelp(AAA)).toBe('The business day the yield applies to, as published by the ECB.')
    expect(validDateHelp(PAR)).toBe('The business day the yield applies to, as published by U.S. Department of the Treasury.')
    expect(validDateHelp(SIM)).toBe('The business day the yield applies to in this scenario.')
  })
})

describe('gapNotes', () => {
  it('says the Treasury never publishes 15Y', () => {
    expect(gapNotes(PAR, ['15Y'])).toEqual([
      'The line skips 15Y: U.S. Department of the Treasury does not publish it for this curve, and gaps are not interpolated.',
    ])
  })

  it('separates maturities that are only missing on the date', () => {
    expect(gapNotes(PAR, ['15Y', '20Y'])).toEqual([
      'The line skips 15Y: U.S. Department of the Treasury does not publish it for this curve, and gaps are not interpolated.',
      'No value for: 20Y on this date (not published by U.S. Department of the Treasury); gaps are not interpolated.',
    ])
  })

  it('has nothing to say without gaps', () => {
    expect(gapNotes(AAA, [])).toEqual([])
  })
})
