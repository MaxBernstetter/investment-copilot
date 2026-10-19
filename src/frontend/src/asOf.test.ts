import { afterEach, describe, expect, it } from 'vitest'
import { localInputToUtc, readAsOf, utcToLocalInput, writeAsOf } from './asOf'

afterEach(() => {
  window.history.replaceState(null, '', '/')
})

describe('asOf', () => {
  it('reads a valid as_of from the URL', () => {
    expect(readAsOf('?as_of=2026-10-01T12:00:00Z')).toBe('2026-10-01T12:00:00Z')
  })

  it('ignores an invalid as_of', () => {
    expect(readAsOf('?as_of=yesterday')).toBeUndefined()
    expect(readAsOf('')).toBeUndefined()
  })

  it('writes and clears as_of in the URL', () => {
    window.history.replaceState(null, '', '/?other=1')

    writeAsOf('2026-10-01T12:00:00.000Z')
    expect(new URLSearchParams(window.location.search).get('as_of')).toBe(
      '2026-10-01T12:00:00.000Z',
    )
    expect(new URLSearchParams(window.location.search).get('other')).toBe('1')

    writeAsOf(undefined)
    expect(new URLSearchParams(window.location.search).has('as_of')).toBe(false)
    expect(new URLSearchParams(window.location.search).get('other')).toBe('1')
  })

  it('round-trips a local datetime through UTC', () => {
    const local = '2026-10-01T12:30:15'

    expect(utcToLocalInput(localInputToUtc(local))).toBe(local)
  })
})
