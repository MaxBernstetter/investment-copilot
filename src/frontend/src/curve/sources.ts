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
}

const UNKNOWN_SOURCE: Source = { publisher: 'the source' }

export function sourceOf(curve: CurveInfo): Source {
  return SOURCES[curve.sourceId] ?? UNKNOWN_SOURCE
}

export function validDateHelp(curve: CurveInfo): string {
  if (curve.simulated) return 'The business day the yield applies to in this scenario.'
  return `The business day the yield applies to, as published by ${sourceOf(curve).publisher}.`
}
