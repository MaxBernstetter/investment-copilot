import type { components } from '../api/schema'

export type ValueChange = components['schemas']['ValueChange']

export type ChangeRow = {
  key: string
  validDate: string
  maturity: string
  oldValue: string
  newValue: string
  delta: string
  reason: string
  source: string
  knownFrom: string
}

const EMPTY = '–'

/** One table row per changed value, in the order the API returns them. */
export function toChangeRows(changes: ValueChange[]): ChangeRow[] {
  return changes.map((change) => ({
    key: `${change.valid_date}-${change.maturity}`,
    validDate: change.valid_date,
    maturity: change.maturity,
    oldValue: change.old_value === null ? EMPTY : String(change.old_value),
    newValue: String(change.new_value),
    delta: formatDeltaBp(change.old_value, change.new_value),
    reason: change.change_reason,
    source: change.source_id ?? EMPTY,
    knownFrom: new Date(change.known_from).toUTCString(),
  }))
}

/** Signed change in basis points, for yields given in percent; a dash when the old value is unknown. */
export function formatDeltaBp(oldValue: number | null, newValue: number): string {
  if (oldValue === null) return EMPTY
  const bp = Math.round((newValue - oldValue) * 100 * 10) / 10
  return `${bp >= 0 ? '+' : '-'}${Math.abs(bp).toFixed(1)} bp`
}
