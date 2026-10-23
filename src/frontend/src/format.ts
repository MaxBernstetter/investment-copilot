import type { CurveInfo } from './curve/fetchCurves'

const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
const MINUS = '−'
const NARROW_NBSP = '\u202F'

/** Shown for a missing value (D2). */
export const EMPTY = '\u2013'

const pad = (n: number) => String(n).padStart(2, '0')

/** Groups the integer digits of a fixed-point string with a comma, e.g. "2376.0" becomes "2,376.0". */
function groupThousands(fixed: string): string {
  const [whole, fraction] = fixed.split('.')
  const grouped = whole.replace(/\B(?=(\d{3})+$)/g, ',')
  return fraction === undefined ? grouped : `${grouped}.${fraction}`
}

/**
 * A UTC instant as `19 Oct 2026, 18:49:25 UTC`, or `19 Oct 2026, 18:49 UTC` with minutes only.
 * Built by hand so the output does not depend on the viewer's locale or time zone.
 */
export function formatUtc(iso: string, precision: 'seconds' | 'minutes' = 'seconds'): string {
  const date = new Date(iso)
  const time = `${pad(date.getUTCHours())}:${pad(date.getUTCMinutes())}`
  const seconds = precision === 'seconds' ? `:${pad(date.getUTCSeconds())}` : ''
  return `${date.getUTCDate()} ${MONTHS[date.getUTCMonth()]} ${date.getUTCFullYear()}, ${time}${seconds} UTC`
}

/** A change in basis points, signed with a true minus and one decimal: `+9.0 bp`, `−2,376.0 bp`. */
export function formatBp(bp: number): string {
  const rounded = Math.sign(bp) * Math.round(Math.abs(bp) * 10) / 10
  if (rounded === 0) return '0.0 bp'
  const sign = rounded > 0 ? '+' : MINUS
  return `${sign}${groupThousands(Math.abs(rounded).toFixed(1))} bp`
}

/** A yield in percent with three decimals and a narrow no-break space (\u202F) before the unit: `2.871 %`. */
export function formatYield(percent: number): string {
  return `${percent.toFixed(3)}${NARROW_NBSP}%`
}

export const RATE_TYPE: Record<CurveInfo['rateType'], string> = { spot: 'Spot', par: 'Par', forward: 'Forward' }

export const COMPOUNDING: Record<CurveInfo['compounding'], string> = {
  continuous: 'continuous',
  annual: 'annual',
  'semi-annual': 'semi-annual',
}

/** `percent` or `%` gives `%`; any other unit is shown as given. */
export function unitSymbol(unit: string): string {
  return unit === 'percent' || unit === '%' ? '%' : unit
}
