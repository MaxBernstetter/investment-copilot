import { useEffect, useState } from 'react'
import { fetchVersions, type VersionsResult } from './fetchVersions'

type VersionHistoryProps = {
  maturity: string
  validDate: string
  asOf?: string
  onClose: () => void
}

const EMPTY = '–'

function utc(iso: string): string {
  return new Date(iso).toUTCString()
}

export default function VersionHistory({ maturity, validDate, asOf, onClose }: VersionHistoryProps) {
  const [result, setResult] = useState<VersionsResult | undefined>(undefined)

  useEffect(() => {
    let active = true
    fetchVersions({ maturity, validDate, asOf }).then((next) => {
      if (active) setResult(next)
    })
    return () => {
      active = false
    }
  }, [maturity, validDate, asOf])

  return (
    <section aria-label={`Version history of ${maturity}`}>
      <h3>
        History of {maturity} on {validDate}
      </h3>
      {result === undefined && <p>Loading…</p>}
      {result?.kind === 'ok' && result.versions.data.versions.length === 0 && (
        <p role="status">No versions known.</p>
      )}
      {result?.kind === 'ok' && result.versions.data.versions.length > 0 && (
        <table>
          <thead>
            <tr>
              <th scope="col">Value</th>
              <th scope="col">Known from</th>
              <th scope="col">Known until</th>
              <th scope="col">Reason</th>
              <th scope="col">Source</th>
              <th scope="col">Run</th>
              <th scope="col">Delivery</th>
            </tr>
          </thead>
          <tbody>
            {result.versions.data.versions.map((version) => (
              <tr key={version.version_id}>
                <td>{version.value}</td>
                <td>{utc(version.known_from)}</td>
                <td>{version.known_to === null ? 'current' : utc(version.known_to)}</td>
                <td>{version.change_reason}</td>
                <td>{version.source_id ?? EMPTY}</td>
                <td>{version.run_id}</td>
                <td>{version.delivery_id ?? EMPTY}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
      {result?.kind === 'offline' && (
        <p role="alert">Backend offline: the YieldLens API is not reachable. Try again later.</p>
      )}
      {result?.kind === 'not-found' && !asOf && (
        <p role="status">No data known for this value.</p>
      )}
      {result?.kind === 'not-found' && asOf && <p>No data known as of {utc(asOf)}</p>}
      {(result?.kind === 'invalid' || result?.kind === 'error') && (
        <p role="alert">{result.detail}</p>
      )}
      <button type="button" onClick={onClose}>
        Close
      </button>
    </section>
  )
}
