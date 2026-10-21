import { useEffect, useMemo, useState } from 'react'
import {
  Alert,
  Card,
  Group,
  NativeSelect,
  SegmentedControl,
  SimpleGrid,
  Skeleton,
  Stack,
  Table,
  TextInput,
  Text,
  Title,
  VisuallyHidden,
} from '@mantine/core'
import StatCard from '../components/StatCard'
import { formatBp, formatUtc, formatYield } from '../format'
import PageHeader from '../layout/PageHeader'
import UncheckedNote from '../quality/UncheckedNote'
import ValueQualityCell from '../quality/ValueQualityCell'
import { fetchSeries, type SeriesResult } from './fetchSeries'
import SeriesChart from './SeriesChart'
import { defaultRange, flaggedCount, MATURITIES, seriesStats } from './seriesData'

const DEFAULT_MATURITY = '10Y'
const EMPTY = '–'

function flaggedCaption(count: number): string {
  return `Flagged: ${count} ${count === 1 ? 'value' : 'values'}. Choose Table to see why.`
}

type SeriesDisplay = 'chart' | 'table'

type SeriesViewProps = {
  curveId: string
  /** The knowledge time shared by all views, set in the header. */
  asOf?: string
}

export default function SeriesView({ curveId, asOf }: SeriesViewProps) {
  const [maturity, setMaturity] = useState(DEFAULT_MATURITY)
  const [range, setRange] = useState(() => defaultRange(new Date()))
  const [display, setDisplay] = useState<SeriesDisplay>('chart')
  const [result, setResult] = useState<SeriesResult | undefined>(undefined)

  useEffect(() => {
    let active = true
    fetchSeries({ curveId, maturity, from: range.from, to: range.to, asOf }).then((next) => {
      if (active) setResult(next)
    })
    return () => {
      active = false
    }
  }, [curveId, maturity, range, asOf])

  const points = useMemo(
    () => (result?.kind === 'ok' ? result.series.data.points : []),
    [result],
  )
  const stats = useMemo(() => seriesStats(points), [points])
  const flagged = useMemo(() => flaggedCount(points), [points])
  const hasUnchecked = points.some((point) => point.quality.status === 'unchecked')

  const headerActions = (
    <>
      <NativeSelect
        label="Maturity"
        data={MATURITIES}
        value={maturity}
        onChange={(event) => setMaturity(event.currentTarget.value)}
      />
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
    </>
  )

  return (
    <Stack component="section" gap="lg">
      <PageHeader
        title="Time series"
        subtitle={`${maturity} yield over valid dates (%)`}
        actions={headerActions}
      />
      {result === undefined && (
        <>
          <Skeleton h={320} />
          <VisuallyHidden>Loading…</VisuallyHidden>
        </>
      )}
      {result?.kind === 'ok' && points.length > 0 && (
        <>
          <SimpleGrid cols={{ base: 2, sm: 4 }}>
            <StatCard label="Last" value={stats.last === undefined ? EMPTY : formatYield(stats.last)} />
            <StatCard label="Min" value={stats.min === undefined ? EMPTY : formatYield(stats.min)} />
            <StatCard label="Max" value={stats.max === undefined ? EMPTY : formatYield(stats.max)} />
            <StatCard
              label="Change over range"
              value={stats.changeBp === undefined ? EMPTY : formatBp(stats.changeBp)}
            />
          </SimpleGrid>
          <Card padding={0}>
            <Card.Section withBorder inheritPadding py="sm">
              <Group justify="space-between" align="center" wrap="wrap" gap="sm">
                <Title order={2}>{maturity} yield (%)</Title>
                <SegmentedControl
                  size="xs"
                  value={display}
                  onChange={(value) => setDisplay(value as SeriesDisplay)}
                  data={[
                    { label: 'Chart', value: 'chart' },
                    { label: 'Table', value: 'table' },
                  ]}
                />
              </Group>
            </Card.Section>
            <Card.Section inheritPadding py="md">
              {display === 'chart' ? (
                <>
                  <SeriesChart points={points} />
                  {flagged > 0 && (
                    <Stack gap={4} mt="sm">
                      <Text size="sm" c="dimmed">{flaggedCaption(flagged)}</Text>
                    </Stack>
                  )}
                </>
              ) : (
                <>
                  <Table.ScrollContainer minWidth={560}>
                    <Table>
                      <Table.Thead>
                        <Table.Tr>
                          <Table.Th scope="col">Valid date</Table.Th>
                          <Table.Th scope="col" ta="right">Yield (%)</Table.Th>
                          <Table.Th scope="col">Quality</Table.Th>
                        </Table.Tr>
                      </Table.Thead>
                      <Table.Tbody>
                        {points.map((point) => (
                          <Table.Tr key={point.valid_date}>
                            <Table.Td>{point.valid_date}</Table.Td>
                            <Table.Td ta="right">{formatYield(point.value)}</Table.Td>
                            <Table.Td>
                              <ValueQualityCell quality={point.quality} maturity={maturity} />
                            </Table.Td>
                          </Table.Tr>
                        ))}
                      </Table.Tbody>
                    </Table>
                  </Table.ScrollContainer>
                  {hasUnchecked && <UncheckedNote />}
                </>
              )}
            </Card.Section>
          </Card>
        </>
      )}
      {result?.kind === 'ok' && points.length === 0 && (
        <Alert variant="light" color="blue" role="status">
          No values in this range.
        </Alert>
      )}
      {result?.kind === 'offline' && (
        <Alert color="red" role="alert">
          Backend offline: the YieldLens API is not reachable. Try again later.
        </Alert>
      )}
      {result?.kind === 'not-found' && !asOf && (
        <Alert variant="light" color="blue" role="status">
          No data known for this maturity.
        </Alert>
      )}
      {result?.kind === 'not-found' && asOf && <Text>No data known as of {formatUtc(asOf)}</Text>}
      {(result?.kind === 'invalid' || result?.kind === 'error') && (
        <Alert color="red" role="alert">
          {result.detail}
        </Alert>
      )}
    </Stack>
  )
}
