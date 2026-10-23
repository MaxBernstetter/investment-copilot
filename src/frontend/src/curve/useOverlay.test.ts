import { act, renderHook } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { AAA, ALL, PAR, SIM } from '../test/catalogue'
import { useOverlay, type OverlayItem } from './useOverlay'

const CATALOGUE = [AAA, ALL, SIM, PAR]
const entry = (curveId: string, validDate: string) => ({ curveId, validDate })
const slots = (items: OverlayItem[]) => items.map((item) => item.slot)

describe('useOverlay', () => {
  it('starts empty', () => {
    const { result } = renderHook(() => useOverlay(CATALOGUE))
    expect(result.current.entries).toEqual([])
  })

  it('adds an entry with the lowest colour slot after the shown one', () => {
    const { result } = renderHook(() => useOverlay(CATALOGUE))

    act(() => result.current.add(entry(AAA.id, '2026-10-15')))
    act(() => result.current.add(entry(ALL.id, '2026-10-15')))

    expect(result.current.entries).toEqual([
      { curveId: AAA.id, validDate: '2026-10-15', slot: 1 },
      { curveId: ALL.id, validDate: '2026-10-15', slot: 2 },
    ])
  })

  it('keeps the colour of the remaining entries when a middle one is removed', () => {
    const { result } = renderHook(() => useOverlay(CATALOGUE))
    act(() => {
      result.current.add(entry(AAA.id, '2026-10-15'))
      result.current.add(entry(AAA.id, '2026-10-14'))
      result.current.add(entry(AAA.id, '2026-10-13'))
    })

    act(() => result.current.remove(entry(AAA.id, '2026-10-14')))

    expect(slots(result.current.entries)).toEqual([1, 3])
    expect(result.current.entries.map((item) => item.validDate)).toEqual(['2026-10-15', '2026-10-13'])
  })

  it('a re-added entry takes the lowest free slot', () => {
    const { result } = renderHook(() => useOverlay(CATALOGUE))
    act(() => {
      result.current.add(entry(AAA.id, '2026-10-15'))
      result.current.add(entry(AAA.id, '2026-10-14'))
      result.current.add(entry(AAA.id, '2026-10-13'))
    })
    act(() => result.current.remove(entry(AAA.id, '2026-10-15')))

    act(() => result.current.add(entry(AAA.id, '2026-10-12')))

    expect(result.current.entries.find((item) => item.validDate === '2026-10-12')?.slot).toBe(1)
  })

  it('caps the overlay at five entries', () => {
    const { result } = renderHook(() => useOverlay(CATALOGUE))
    const dates = ['2026-10-15', '2026-10-14', '2026-10-13', '2026-10-12', '2026-10-11', '2026-10-10']
    act(() => dates.forEach((date) => result.current.add(entry(AAA.id, date))))

    expect(result.current.entries).toHaveLength(5)
    expect(result.current.entries.map((item) => item.validDate)).not.toContain('2026-10-10')
    expect(result.current.canAdd(entry(ALL.id, '2026-10-10'))).toBe('full')
  })

  it('rejects a duplicate curve and date', () => {
    const { result } = renderHook(() => useOverlay(CATALOGUE))
    act(() => result.current.add(entry(AAA.id, '2026-10-15')))

    expect(result.current.canAdd(entry(AAA.id, '2026-10-15'))).toBe('duplicate')
    act(() => result.current.add(entry(AAA.id, '2026-10-15')))
    expect(result.current.entries).toHaveLength(1)
  })

  it('treats the same date on another curve as a new entry', () => {
    const { result } = renderHook(() => useOverlay(CATALOGUE))
    act(() => result.current.add(entry(AAA.id, '2026-10-15')))

    expect(result.current.canAdd(entry(ALL.id, '2026-10-15'))).toBe('ok')
  })

  it('hides entries whose curve left the catalogue and keeps them for when it returns', () => {
    const { result, rerender } = renderHook(({ catalogue }) => useOverlay(catalogue), {
      initialProps: { catalogue: CATALOGUE },
    })
    act(() => result.current.add(entry(PAR.id, '2026-10-15')))

    rerender({ catalogue: [AAA, ALL] })
    expect(result.current.entries).toEqual([])

    rerender({ catalogue: CATALOGUE })
    expect(result.current.entries).toEqual([{ curveId: PAR.id, validDate: '2026-10-15', slot: 1 }])
  })
})
