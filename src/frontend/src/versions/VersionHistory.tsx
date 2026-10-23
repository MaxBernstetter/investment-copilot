import { useEffect, useState } from 'react'
import { Alert, Badge, Drawer, Text } from '@mantine/core'
import DataTable from '../components/DataTable'
import { formatUtc, formatYield } from '../format'
import { reasonBadgeProps } from '../theme'
import { fetchVersions, type VersionsResult } from './fetchVersions'

type VersionHistoryProps = {
  curveId: string
  maturity: string
  validDate: string
  asOf?: string
  opened: boolean
  onClose: () => void
}

const EMPTY = '–'

export default function VersionHistory({
  curveId,
  maturity,
  validDate,
  asOf,
  opened,
  onClose,
}: VersionHistoryProps) {
  const [result, setResult] = useState<VersionsResult | undefined>(undefined)

  useEffect(() => {
    if (!opened) return
    let active = true
    setResult(undefined)
    fetchVersions({ curveId, maturity, validDate, asOf }).then((next) => {
      if (active) setResult(next)
    })
    return () => {
      active = false
    }
  }, [curveId, maturity, validDate, asOf, opened])

  return (
    <Drawer.Root position="right" size="90%" opened={opened} onClose={onClose}>
      <Drawer.Overlay />
      <Drawer.Content>
        {/* Drawer.Header defaults to <header>, a banner landmark that duplicates the app header. */}
        <Drawer.Header component="div">
          <Drawer.Title>{`History of ${maturity} on ${validDate}`}</Drawer.Title>
          <Drawer.CloseButton aria-label="Close" />
        </Drawer.Header>
        <Drawer.Body>
          {result === undefined && <Text>Loading…</Text>}
          {result?.kind === 'ok' && result.versions.data.versions.length === 0 && (
            <Alert variant="light" color="blue" role="status">
              No versions known.
            </Alert>
          )}
          {result?.kind === 'ok' && result.versions.data.versions.length > 0 && (
            <DataTable
              striped
              columns={[
                {
                  id: 'value',
                  header: 'Value',
                  align: 'right',
                  cell: (version) => formatYield(version.value),
                  filterText: (version) => formatYield(version.value),
                },
                {
                  id: 'known-from',
                  header: 'Known from',
                  cell: (version) => formatUtc(version.known_from),
                  filterText: (version) => formatUtc(version.known_from),
                },
                {
                  id: 'known-until',
                  header: 'Known until',
                  cell: (version) => (version.known_to === null ? 'current' : formatUtc(version.known_to)),
                  filterText: (version) => (version.known_to === null ? 'current' : formatUtc(version.known_to)),
                },
                {
                  id: 'reason',
                  header: 'Reason',
                  cell: (version) => <Badge {...reasonBadgeProps(version.change_reason)}>{version.change_reason}</Badge>,
                  filterText: (version) => version.change_reason,
                },
                {
                  id: 'source',
                  header: 'Source',
                  cell: (version) => version.source_id ?? EMPTY,
                  filterText: (version) => version.source_id ?? '',
                },
                {
                  id: 'run',
                  header: 'Run',
                  cell: (version) => (
                    <Text span inherit display="inline-block" miw="max-content">
                      {version.run_id}
                    </Text>
                  ),
                  filterText: (version) => version.run_id,
                },
                {
                  id: 'delivery',
                  header: 'Delivery',
                  cell: (version) => version.delivery_id ?? EMPTY,
                  filterText: (version) => version.delivery_id ?? '',
                },
              ]}
              rows={result.versions.data.versions}
              rowKey={(version) => String(version.version_id)}
            />
          )}
          {result?.kind === 'offline' && (
            <Alert color="red" role="alert">
              Backend offline: the YieldLens API is not reachable. Try again later.
            </Alert>
          )}
          {result?.kind === 'not-found' && !asOf && (
            <Alert variant="light" color="blue" role="status">
              No data known for this value.
            </Alert>
          )}
          {result?.kind === 'not-found' && asOf && <Text>No data known as of {formatUtc(asOf)}</Text>}
          {(result?.kind === 'invalid' || result?.kind === 'error') && (
            <Alert color="red" role="alert">
              {result.detail}
            </Alert>
          )}
        </Drawer.Body>
      </Drawer.Content>
    </Drawer.Root>
  )
}
