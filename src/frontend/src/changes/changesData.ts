import type { components } from '../api/schema'
import { formatBp, formatUtc, formatYield } from '../format'

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
    oldValue: change.old_value === null ? EMPTY : formatYield(change.old_value),
    newValue: formatYield(change.new_value),
    delta:
      change.old_value === null ? EMPTY : formatBp((change.new_value - change.old_value) * 100),
    reason: change.change_reason,
    source: change.source_id ?? EMPTY,
    knownFrom: formatUtc(change.known_from),
  }))
}
