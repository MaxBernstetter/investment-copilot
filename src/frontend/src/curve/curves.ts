import type { CurveInfo } from './fetchCurves'

export const DEFAULT_CURVE_ID = 'ecb-aaa-spot'

const PARAM = 'curve'

/** The `curve` URL parameter as given; a missing one gives the default id. Resolution against the catalogue is resolveCurve's job. */
export function readCurveId(search: string): string {
  return new URLSearchParams(search).get(PARAM) || DEFAULT_CURVE_ID
}

/** Sets the `curve` URL parameter without adding a history entry. */
export function writeCurveId(id: string): void {
  const url = new URL(window.location.href)
  url.searchParams.set(PARAM, id)
  window.history.replaceState(null, '', url)
}

/**
 * The curve for an id: the exact match, else the default curve, else the first published curve,
 * else the first curve. Undefined only for an empty catalogue.
 */
export function resolveCurve(catalogue: readonly CurveInfo[], id: string): CurveInfo | undefined {
  return (
    catalogue.find((curve) => curve.id === id) ??
    catalogue.find((curve) => curve.id === DEFAULT_CURVE_ID) ??
    catalogue.find((curve) => !curve.simulated) ??
    catalogue[0]
  )
}

export type CurveSelectGroup = { group: 'Published' | 'Simulated'; items: { value: string; label: string }[] }

/** The select options: published curves first, then simulated, each in catalogue order; empty groups are dropped. */
export function curveSelectData(catalogue: readonly CurveInfo[]): CurveSelectGroup[] {
  const option = (curve: CurveInfo) => ({ value: curve.id, label: curve.label })
  const published = catalogue.filter((curve) => !curve.simulated).map(option)
  const simulated = catalogue.filter((curve) => curve.simulated).map(option)
  return [
    ...(published.length > 0 ? [{ group: 'Published' as const, items: published }] : []),
    ...(simulated.length > 0 ? [{ group: 'Simulated' as const, items: simulated }] : []),
  ]
}
