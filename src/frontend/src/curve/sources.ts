import type { CurveInfo } from './fetchCurves'

export type Source = { publisher: string; termsUrl?: string }

/** Publisher and reuse-terms link per catalogue source id. */
export const SOURCES: Record<string, Source> = {
  ecb: {
    publisher: 'the ECB',
    termsUrl: 'https://www.ecb.europa.eu/services/using-our-site/disclaimer/html/index.en.html',
  },
  // The only scenario curve simulates the ECB AAA curve, so it names the ECB without a terms link.
  scenario: { publisher: 'the ECB' },
  // The US Treasury publishes par yields openly, so the publisher has no reuse-terms link.
  ust: { publisher: 'U.S. Department of the Treasury' },
}

const UNKNOWN_SOURCE: Source = { publisher: 'the source' }

export function sourceOf(curve: CurveInfo): Source {
  return SOURCES[curve.sourceId] ?? UNKNOWN_SOURCE
}

export function validDateHelp(curve: CurveInfo): string {
  if (curve.simulated) return 'The business day the yield applies to in this scenario.'
  return `The business day the yield applies to, as published by ${sourceOf(curve).publisher}.`
}

/** Maturities a source never publishes, by catalogue source id; the curve grid has them for other sources. */
const NEVER_PUBLISHED: Record<string, readonly string[]> = {
  ust: ['15Y'],
}

/**
 * Why the chart has gaps: one sentence for the maturities the source never publishes, one for those
 * missing on this date. Lines are never drawn across a gap.
 */
export function gapNotes(curve: CurveInfo, missing: readonly string[]): string[] {
  const { publisher } = sourceOf(curve)
  const never = missing.filter((maturity) => NEVER_PUBLISHED[curve.sourceId]?.includes(maturity))
  const absent = missing.filter((maturity) => !never.includes(maturity))
  return [
    ...(never.length > 0
      ? [`The line skips ${never.join(', ')}: ${publisher} does not publish it for this curve, and gaps are not interpolated.`]
      : []),
    ...(absent.length > 0
      ? [`No value for: ${absent.join(', ')} on this date (not published by ${publisher}); gaps are not interpolated.`]
      : []),
  ]
}
