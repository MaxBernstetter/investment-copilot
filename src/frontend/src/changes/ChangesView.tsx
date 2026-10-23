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
  TextInput,
  Tooltip,
  VisuallyHidden,
} from '@mantine/core'
import { IconInfoCircle } from '@tabler/icons-react'
import { localInputToUtc } from '../asOf'
import DataTable from '../components/DataTable'
import PageHeader from '../layout/PageHeader'
import { reasonBadgeProps } from '../theme'
import { defaultRange } from '../series/seriesData'
import ChangesEmptyState from './ChangesEmptyState'
import { fetchChanges, type ChangesResult } from './fetchChanges'
import { defaultSinceInput, toChangeRows } from './changesData'

type ChangesViewProps = {
  curveId: string
  /** The knowledge time shared by all views, set in the header. */
  asOf?: string
}

const COMPARE_FROM_TOOLTIP =
  'The earlier knowledge time. Changes known after it, up to Known as of, are listed.'

export default function ChangesView({ curveId, asOf }: ChangesViewProps) {
  const [range, setRange] = useState(() => defaultRange(new Date()))
  const [sinceInput, setSinceInput] = useState(() => defaultSinceInput(new Date(), asOf))
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
          <DataTable
            striped
            columns={[
              { id: 'valid-date', header: 'Valid date', cell: (row) => row.validDate, filterText: (row) => row.validDate },
              { id: 'maturity', header: 'Maturity', cell: (row) => row.maturity, filterText: (row) => row.maturity },
              { id: 'old', header: 'Old (%)', align: 'right', cell: (row) => row.oldValue, filterText: (row) => row.oldValue },
              { id: 'new', header: 'New (%)', align: 'right', cell: (row) => row.newValue, filterText: (row) => row.newValue },
              { id: 'delta', header: 'Change (bp)', align: 'right', cell: (row) => row.delta, filterText: (row) => row.delta },
              {
                id: 'reason',
                header: 'Reason',
                cell: (row) => <Badge {...reasonBadgeProps(row.reason)}>{row.reason}</Badge>,
                filterText: (row) => row.reason,
              },
              { id: 'source', header: 'Source', cell: (row) => row.source, filterText: (row) => row.source },
              { id: 'known-from', header: 'Known from', cell: (row) => row.knownFrom, filterText: (row) => row.knownFrom },
            ]}
            rows={toChangeRows(result.changes.data.changes)}
            rowKey={(row) => row.key}
          />
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
