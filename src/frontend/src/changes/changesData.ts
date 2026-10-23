import type { components } from '../api/schema'
import { utcToLocalInput } from '../asOf'
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
  oldRaw: number | null
  newRaw: number
  deltaRaw: number | null
  knownFromIso: string
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
    oldRaw: change.old_value,
    newRaw: change.new_value,
    deltaRaw: change.old_value === null ? null : (change.new_value - change.old_value) * 100,
    knownFromIso: change.known_from.slice(0, 16),
  }))
}

const WEEK_MS = 7 * 24 * 60 * 60 * 1000

/**
 * The prefilled "Compare from" (a `datetime-local` value): one week before the knowledge time the
 * views show, so the table lists what the platform learned in the last week.
 */
export function defaultSinceInput(now: Date, asOf?: string): string {
  const shown = asOf === undefined ? now : new Date(asOf)
  const week = new Date(shown.getTime() - WEEK_MS)
  week.setSeconds(0, 0)
  return utcToLocalInput(week.toISOString())
}
