const PARAM = 'as_of'

/** The knowledge time (UTC ISO string) from the `as_of` URL parameter, if it is a valid date. */
export function readAsOf(search: string): string | undefined {
  const value = new URLSearchParams(search).get(PARAM)
  if (value === null || isNaN(Date.parse(value))) return undefined
  return value
}

/** Sets or removes the `as_of` URL parameter without adding a history entry. */
export function writeAsOf(asOf: string | undefined): void {
  const url = new URL(window.location.href)
  if (asOf === undefined) {
    url.searchParams.delete(PARAM)
  } else {
    url.searchParams.set(PARAM, asOf)
  }
  window.history.replaceState(null, '', url)
}

/** Converts a `datetime-local` value, read as local time, to a UTC ISO string. */
export function localInputToUtc(value: string): string {
  return new Date(value).toISOString()
}

/** Converts a UTC ISO string to a local `datetime-local` value with seconds. */
export function utcToLocalInput(iso: string): string {
  const date = new Date(iso)
  const pad = (n: number) => String(n).padStart(2, '0')
  return (
    `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}` +
    `T${pad(date.getHours())}:${pad(date.getMinutes())}:${pad(date.getSeconds())}`
  )
}
