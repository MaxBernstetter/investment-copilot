import { useEffect, useState } from 'react'
import {
  ActionIcon,
  Alert,
  Badge,
  Card,
  Group,
  Input,
  Skeleton,
  Stack,
  Table,
  TextInput,
  Tooltip,
  VisuallyHidden,
} from '@mantine/core'
import { IconInfoCircle } from '@tabler/icons-react'
import { localInputToUtc } from '../asOf'
import PageHeader from '../layout/PageHeader'
import { defaultRange } from '../series/seriesData'
import ChangesEmptyState from './ChangesEmptyState'
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

const COMPARE_FROM_TOOLTIP =
  'The earlier knowledge time. Changes known after it, up to Known as of, are listed.'

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
    <Stack component="section" gap="lg">
      <PageHeader
        title="Changes"
        subtitle="What changed in the data between two knowledge times"
      />
      <Card>
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
          <Stack gap={4}>
            <Group gap={4} wrap="nowrap" align="center">
              <Input.Label htmlFor="changes-compare-from">Compare from (known as of)</Input.Label>
              <Tooltip
                label={COMPARE_FROM_TOOLTIP}
                events={{ hover: true, focus: true, touch: true }}
              >
                <ActionIcon variant="subtle" size="xs" aria-label="Earlier knowledge time help">
                  <IconInfoCircle size={14} />
                </ActionIcon>
              </Tooltip>
            </Group>
            <TextInput
              id="changes-compare-from"
              type="datetime-local"
              step={1}
              description="Your local time, shown in UTC elsewhere"
              value={sinceInput}
              onChange={(event) => setSinceInput(event.currentTarget.value)}
            />
          </Stack>
        </Group>
      </Card>
      {since === undefined && (
        <ChangesEmptyState
          title="Pick a starting point"
          description="Choose the earlier knowledge time to compare."
        />
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
        <Card>
          <Table.ScrollContainer minWidth={900}>
            <Table striped>
              <Table.Thead>
                <Table.Tr>
                  <Table.Th scope="col">Valid date</Table.Th>
                  <Table.Th scope="col">Maturity</Table.Th>
                  <Table.Th scope="col" ta="right">Old (%)</Table.Th>
                  <Table.Th scope="col" ta="right">New (%)</Table.Th>
                  <Table.Th scope="col" ta="right">Change (bp)</Table.Th>
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
                    <Table.Td ta="right">{row.oldValue}</Table.Td>
                    <Table.Td ta="right">{row.newValue}</Table.Td>
                    <Table.Td ta="right">{row.delta}</Table.Td>
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
        </Card>
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
