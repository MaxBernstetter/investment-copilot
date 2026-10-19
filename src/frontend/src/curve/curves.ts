export type CurveOption = { id: string; label: string; isSimulated: boolean }

const REAL_CURVE: CurveOption = { id: 'ecb-aaa-spot', label: 'ECB euro area AAA spot', isSimulated: false }

export const CURVES: readonly CurveOption[] = [
  REAL_CURVE,
  { id: 'ecb-aaa-spot-sim', label: 'Simulated: ECB euro area AAA spot (scenario data)', isSimulated: true },
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
