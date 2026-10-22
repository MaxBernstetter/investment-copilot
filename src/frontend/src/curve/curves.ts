import type { CurveInfo } from './fetchCurves'

export type CurveOption = { id: string; label: string; isSimulated: boolean }

const REAL_CURVE: CurveOption = { id: 'ecb-aaa-spot', label: 'ECB euro area AAA spot', isSimulated: false }

export const CURVES: readonly CurveOption[] = [
  REAL_CURVE,
  { id: 'ecb-aaa-spot-sim', label: 'ECB euro area AAA spot (scenario data)', isSimulated: true },
]

export const DEFAULT_CURVE_ID = REAL_CURVE.id

const PARAM = 'curve'

/** The curve with this id; an unknown id gives the real curve. */
export function curveById(id: string): CurveOption {
  return CURVES.find((curve) => curve.id === id) ?? REAL_CURVE
}

/** The curve id from the `curve` URL parameter; a missing or unknown id gives the default. */
export function readCurveId(search: string): string {
  return curveById(new URLSearchParams(search).get(PARAM) ?? '').id
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
