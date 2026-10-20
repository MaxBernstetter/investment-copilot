import type { components } from '../api/schema'
import { CHART_COLORS } from '../theme'

export type CurvePoint = components['schemas']['CurvePoint']

/** A curve on the chart, labelled by its valid date. */
export type LabelledCurve = { label: string; points: CurvePoint[] }

const PALETTE: readonly string[] = CHART_COLORS

/**
 * One row per maturity in grid order, with one key per curve label.
 * A maturity a curve does not publish is null, so the chart leaves a gap.
 */
export function overlayRows(curves: LabelledCurve[]): Record<string, string | number | null>[] {
  const maturities = [...new Set(curves.flatMap(({ points }) => points.map((p) => p.maturity)))]
  return maturities.map((maturity) => {
    const row: Record<string, string | number | null> = { maturity }
    for (const { label, points } of curves) {
      row[label] = points.find((point) => point.maturity === maturity)?.value ?? null
    }
    return row
  })
}

/** One series per curve, named by its label so the legend shows the valid date. */
export function overlaySeries(curves: LabelledCurve[]): { name: string; color: string }[] {
  return curves.map(({ label }, i) => ({ name: label, color: PALETTE[i % PALETTE.length] }))
}

/** Maturities on the grid without a published value as of the answer's knowledge time. */
export function missingMaturities(points: CurvePoint[]): string[] {
  return points.filter((point) => point.value === null).map((point) => point.maturity)
}
