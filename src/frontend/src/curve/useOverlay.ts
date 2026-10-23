import { useCallback, useMemo, useState } from 'react'
import { entryKey, nextSlot, type OverlayEntry } from './curveData'
import type { CurveInfo } from './fetchCurves'

/** Pinned curves on top of the shown one, so the chart has at most six series. */
export const MAX_OVERLAYS = 5

/** An overlay entry with the colour slot it was given when added (1 to 5; slot 0 is the shown curve). */
export type OverlayItem = OverlayEntry & { slot: number }

/** Why an entry cannot be added: already pinned, or the overlay is full. */
export type CanAdd = 'ok' | 'duplicate' | 'full'

const same = (a: OverlayEntry, b: OverlayEntry) => entryKey(a) === entryKey(b)

/**
 * The pinned overlay entries, owned above the curve view so they survive a curve switch.
 * Entries whose curve is no longer in the catalogue are hidden, not removed.
 */
export function useOverlay(catalogue: readonly CurveInfo[]) {
  const [stored, setStored] = useState<OverlayItem[]>([])
  const known = useMemo(() => new Set(catalogue.map((curve) => curve.id)), [catalogue])
  const entries = useMemo(() => stored.filter((entry) => known.has(entry.curveId)), [stored, known])

  const canAdd = useCallback(
    (entry: OverlayEntry): CanAdd => {
      if (entries.some((current) => same(current, entry))) return 'duplicate'
      return entries.length >= MAX_OVERLAYS ? 'full' : 'ok'
    },
    [entries],
  )

  const add = useCallback(
    (entry: OverlayEntry) => {
      setStored((current) => {
        const live = current.filter((item) => known.has(item.curveId))
        if (live.some((item) => same(item, entry)) || live.length >= MAX_OVERLAYS) return current
        return [...live, { curveId: entry.curveId, validDate: entry.validDate, slot: nextSlot([0, ...live.map((item) => item.slot)]) }]
      })
    },
    [known],
  )

  const remove = useCallback((entry: OverlayEntry) => {
    setStored((current) => current.filter((item) => !same(item, entry)))
  }, [])

  return { entries, add, remove, canAdd }
}

export type OverlayState = ReturnType<typeof useOverlay>
