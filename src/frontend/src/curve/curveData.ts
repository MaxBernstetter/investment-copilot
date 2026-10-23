import type { components } from '../api/schema'
import { CHART_COLORS } from '../theme'
import type { CurveInfo } from './fetchCurves'

export type CurvePoint = components['schemas']['CurvePoint']

/** One curve on the overlay: a catalogue curve at one valid date. */
export type OverlayEntry = { curveId: string; validDate: string }

/** The stable key of an overlay entry, safe as a chart data key (no dots). */
export function entryKey(entry: OverlayEntry): string {
  return `${entry.curveId}|${entry.validDate}`
}

/**
 * The x-axis label for a tenor in months: 6 is "6M", 12 is "1Y", 360 is "30Y", 1.5 is "1.5M".
 */
export function monthsLabel(months: number): string {
  return months % 12 === 0 && months >= 12 ? `${months / 12}Y` : `${months}M`
}

/**
 * A curve on the chart: its entry key, its legend label, its points and its colour slot.
 * The shown curve is slot 0; an overlay keeps the slot it was given when added.
 */
export type LabelledCurve = { key: string; label: string; points: CurvePoint[]; slot: number }

/** The lowest colour slot not in use. */
export function nextSlot(used: number[]): number {
  let slot = 0
  while (used.includes(slot)) slot++
  return slot
}

const PALETTE: readonly string[] = CHART_COLORS

/** The colour of a slot; the palette repeats after six slots, and the cap keeps the slots below that. */
export function slotColor(slot: number): string {
  return PALETTE[slot % PALETTE.length]
}

/**
 * One row per tenor in months, sorted ascending, with one key per curve key.
 * A tenor a curve does not publish is null, so the chart leaves a gap.
 */
export function overlayRows(curves: LabelledCurve[]): Record<string, string | number | null>[] {
  const months = [...new Set(curves.flatMap(({ points }) => points.map((p) => p.months)))].sort((a, b) => a - b)
  const valuesByCurve = curves.map(({ key, points }) => ({
    key,
    values: new Map(points.map((point) => [point.months, point.value])),
  }))
  return months.map((tenor) => {
    const row: Record<string, string | number | null> = { months: tenor }
    for (const { key, values } of valuesByCurve) {
      row[key] = values.get(tenor) ?? null
    }
    return row
  })
}

/** One series per curve, named by its key and coloured by its slot; the legend shows its label. */
export function overlaySeries(curves: LabelledCurve[]): { name: string; label: string; color: string }[] {
  return curves.map(({ key, label, slot }) => ({ name: key, label, color: slotColor(slot) }))
}

/** Maturities on the grid without a published value as of the answer's knowledge time. */
export function missingMaturities(points: CurvePoint[]): string[] {
  return points.filter((point) => point.value === null).map((point) => point.maturity)
}

/** Maturities whose value has an info or warn flag, in grid order. */
export function flaggedMaturities(points: CurvePoint[]): string[] {
  return points
    .filter((point) => point.quality?.status === 'info' || point.quality?.status === 'warn')
    .map((point) => point.maturity)
}

const yieldAt = (points: CurvePoint[], maturity: string): number | undefined => {
  const value = points.find((point) => point.maturity === maturity)?.value
  return value === null || value === undefined ? undefined : value
}

/** The 10Y yield in percent, or undefined when it is not published. */
export function yield10y(points: CurvePoint[]): number | undefined {
  return yieldAt(points, '10Y')
}

/** Hint under the 10Y yield card: missing, or flagged info/warn. */
export function tenYearHint(points: CurvePoint[]): string | undefined {
  if (yield10y(points) === undefined) return 'Not available'
  if (flaggedMaturities(points).includes('10Y')) return 'Value flagged'
  return undefined
}

/** Why the curves on one chart are not directly comparable, or undefined when their conventions agree. */
export type ComparabilityIssue = 'rate-type' | 'compounding' | 'both'

/** Whether the curves differ in rate type, compounding, or both. Simulated curves follow the same rule. */
export function comparabilityIssue(curves: readonly CurveInfo[]): ComparabilityIssue | undefined {
  const rateDiffers = new Set(curves.map((curve) => curve.rateType)).size > 1
  const compoundingDiffers = new Set(curves.map((curve) => curve.compounding)).size > 1
  if (rateDiffers && compoundingDiffers) return 'both'
  if (rateDiffers) return 'rate-type'
  if (compoundingDiffers) return 'compounding'
  return undefined
}

/**
 * The distinct catalogue curves of some overlay entries, in order of first appearance.
 * An entry whose curve is not in the catalogue is skipped.
 */
export function distinctCurves(entries: readonly OverlayEntry[], catalogue: readonly CurveInfo[]): CurveInfo[] {
  const byId = new Map(catalogue.map((curve) => [curve.id, curve]))
  const seen = new Set<string>()
  const curves: CurveInfo[] = []
  for (const { curveId } of entries) {
    const curve = byId.get(curveId)
    if (curve === undefined || seen.has(curveId)) continue
    seen.add(curveId)
    curves.push(curve)
  }
  return curves
}
