import { useEffect, useState } from 'react'
import { Alert, Badge, Group, Paper, Skeleton, Stack, Table, TextInput, Text, VisuallyHidden } from '@mantine/core'
import { localInputToUtc } from '../asOf'
import PageHeader from '../layout/PageHeader'
import { defaultRange } from '../series/seriesData'
import { fetchChanges, type ChangesResult } from './fetchChanges'
import { toChangeRows } from './changesData'

type ChangesViewProps = {
  curveId: string
  /** The knowledge time shared by all views, set in the header. */
  asOf?: string
}

const REASON_COLORS: Record<string, string> = {
  correction: 'orange',
  revision: 'blue',
}

export default function ChangesView({ curveId, asOf }: ChangesViewProps) {
  const [range, setRange] = useState(() => defaultRange(new Date()))
  const [sinceInput, setSinceInput] = useState('')
  const [result, setResult] = useState<ChangesResult | undefined>(undefined)

  const since = sinceInput ? localInputToUtc(sinceInput) : undefined

  useEffect(() => {
    if (since === undefined) return
    let active = true
    fetchChanges({ curveId, from: range.from, to: range.to, since, asOf }).then((next) => {
      if (active) setResult(next)
    })
    return () => {
      active = false
    }
  }, [curveId, range, since, asOf])

  return (
    <Stack component="section" gap="md">
      <PageHeader title="Changes between two knowledge states" />
      <Group gap="sm" align="flex-end">
        <TextInput
          type="date"
          label="From"
          value={range.from}
          onChange={(event) => {
            if (event.currentTarget.value) setRange({ ...range, from: event.currentTarget.value })
          }}
        />
        <TextInput
          type="date"
          label="To"
          value={range.to}
          onChange={(event) => {
            if (event.currentTarget.value) setRange({ ...range, to: event.currentTarget.value })
          }}
        />
        <TextInput
          type="datetime-local"
          step={1}
          label="Compare from (known as of)"
          description="Your local time, shown in UTC elsewhere"
          value={sinceInput}
          onChange={(event) => setSinceInput(event.currentTarget.value)}
        />
      </Group>
      {since === undefined && (
        <Text role="status">Choose the earlier knowledge time to compare.</Text>
      )}
      {since !== undefined && result === undefined && (
        <>
          <Skeleton h={160} />
          <VisuallyHidden>Loading…</VisuallyHidden>
        </>
      )}
      {since !== undefined && result?.kind === 'ok' && result.changes.data.changes.length === 0 && (
        <Alert variant="light" color="blue" role="status">
          No changes between these knowledge times.
        </Alert>
      )}
      {since !== undefined && result?.kind === 'ok' && result.changes.data.changes.length > 0 && (
        <Paper withBorder p="md">
          <Table.ScrollContainer minWidth={900}>
            <Table striped highlightOnHover style={{ fontVariantNumeric: 'tabular-nums' }}>
              <Table.Thead>
                <Table.Tr>
                  <Table.Th scope="col">Valid date</Table.Th>
                  <Table.Th scope="col">Maturity</Table.Th>
                  <Table.Th scope="col">Old value</Table.Th>
                  <Table.Th scope="col">New value</Table.Th>
                  <Table.Th scope="col">Change</Table.Th>
                  <Table.Th scope="col">Reason</Table.Th>
                  <Table.Th scope="col">Source</Table.Th>
                  <Table.Th scope="col">Known from</Table.Th>
                </Table.Tr>
              </Table.Thead>
              <Table.Tbody>
                {toChangeRows(result.changes.data.changes).map((row) => (
                  <Table.Tr key={row.key}>
                    <Table.Td>{row.validDate}</Table.Td>
                    <Table.Td>{row.maturity}</Table.Td>
                    <Table.Td>{row.oldValue}</Table.Td>
                    <Table.Td>{row.newValue}</Table.Td>
                    <Table.Td>{row.delta}</Table.Td>
                    <Table.Td>
                      <Badge color={REASON_COLORS[row.reason] ?? 'gray'} variant="light">
                        {row.reason}
                      </Badge>
                    </Table.Td>
                    <Table.Td>{row.source}</Table.Td>
                    <Table.Td>{row.knownFrom}</Table.Td>
                  </Table.Tr>
                ))}
              </Table.Tbody>
            </Table>
          </Table.ScrollContainer>
        </Paper>
      )}
      {since !== undefined && result?.kind === 'offline' && (
        <Alert color="red" role="alert">
          Backend offline: the YieldLens API is not reachable. Try again later.
        </Alert>
      )}
      {since !== undefined && result?.kind === 'not-found' && (
        <Alert variant="light" color="blue" role="status">
          {result.detail}
        </Alert>
      )}
      {since !== undefined && (result?.kind === 'invalid' || result?.kind === 'error') && (
        <Alert color="red" role="alert">
          {result.detail}
        </Alert>
      )}
    </Stack>
  )
}
