import { useEffect, useState } from 'react'
import { Alert, Badge, Drawer, Table, Text } from '@mantine/core'
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
    <Drawer.Root position="right" size="lg" opened={opened} onClose={onClose}>
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
            <Table.ScrollContainer
              minWidth={600}
              scrollAreaProps={{ viewportProps: { tabIndex: 0 } }}
            >
              <Table striped>
                <Table.Thead>
                  <Table.Tr>
                    <Table.Th scope="col" ta="right">Value</Table.Th>
                    <Table.Th scope="col">Known from</Table.Th>
                    <Table.Th scope="col">Known until</Table.Th>
                    <Table.Th scope="col">Reason</Table.Th>
                    <Table.Th scope="col">Source</Table.Th>
                    <Table.Th scope="col">Run</Table.Th>
                    <Table.Th scope="col">Delivery</Table.Th>
                  </Table.Tr>
                </Table.Thead>
                <Table.Tbody>
                  {result.versions.data.versions.map((version) => (
                    <Table.Tr key={version.version_id}>
                      <Table.Td ta="right">{formatYield(version.value)}</Table.Td>
                      <Table.Td>{formatUtc(version.known_from)}</Table.Td>
                      <Table.Td>{version.known_to === null ? 'current' : formatUtc(version.known_to)}</Table.Td>
                      <Table.Td>
                        <Badge {...reasonBadgeProps(version.change_reason)}>
                          {version.change_reason}
                        </Badge>
                      </Table.Td>
                      <Table.Td>{version.source_id ?? EMPTY}</Table.Td>
                      <Table.Td>{version.run_id}</Table.Td>
                      <Table.Td>{version.delivery_id ?? EMPTY}</Table.Td>
                    </Table.Tr>
                  ))}
                </Table.Tbody>
              </Table>
            </Table.ScrollContainer>
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
