import { useEffect, useMemo, useState } from 'react'
import {
  Alert,
  Box,
  Button,
  Card,
  EmptyState,
  Group,
  NativeSelect,
  SegmentedControl,
  SimpleGrid,
  Skeleton,
  Stack,
  Text,
  TextInput,
  Title,
  VisuallyHidden,
} from '@mantine/core'
import { IconAlertTriangle } from '@tabler/icons-react'
import DataTable from '../components/DataTable'
import { fetchMeasures, type MeasuresResult } from '../curve/fetchMeasures'
import { MEASURE_LABEL, type MeasureKey } from '../curve/measuresData'
import StatCard from '../components/StatCard'
import { EMPTY, formatBp, formatUtc, formatYield } from '../format'
import PageHeader from '../layout/PageHeader'
import UncheckedNote from '../quality/UncheckedNote'
import { STATUS_LABEL } from '../quality/qualityData'
import ValueQualityCell from '../quality/ValueQualityCell'
import { fetchSeries, type SeriesResult } from './fetchSeries'
import MeasureCard from './MeasureCard'
import SeriesChart from './SeriesChart'
import { choiceValue, measureInputsText, MEASURES, parseChoice } from './measureSeries'
import { defaultRange, flaggedCaption, flaggedCount, MATURITIES, seriesChart, seriesStats } from './seriesData'

const DEFAULT_SELECTION = choiceValue({ kind: 'yield', maturity: '10Y' })
const SELECT_DATA = [
  {
    group: 'Yields',
    items: MATURITIES.map((maturity) => ({ value: choiceValue({ kind: 'yield', maturity }), label: maturity })),
  },
  {
    group: 'Measures',
    items: MEASURES.map(({ key, label }) => ({ value: choiceValue({ kind: 'measure', key }), label })),
  },
]

type SeriesDisplay = 'chart' | 'table'

/** One answer, tagged with the series it is for. */
type Loaded =
  | { kind: 'yield'; maturity: string; result: SeriesResult }
  | { kind: 'measure'; key: MeasureKey; result: MeasuresResult }

type SeriesViewProps = {
  curveId: string
  /** The knowledge time shared by all views, set in the header. */
  asOf?: string
}

/** Identifies one request, so a stale answer is never shown for a newer selection, range or retry. */
function requestKey(selection: string, range: { from: string; to: string }, asOf: string | undefined, attempt: number) {
  return [selection, range.from, range.to, asOf ?? '', attempt].join('|')
}

function loadSelection(
  selection: string,
  curveId: string,
  range: { from: string; to: string },
  asOf: string | undefined,
): Promise<Loaded> {
  const choice = parseChoice(selection)
  if (choice.kind === 'yield') {
    return fetchSeries({ curveId, maturity: choice.maturity, from: range.from, to: range.to, asOf }).then(
      (result): Loaded => ({ kind: 'yield', maturity: choice.maturity, result }),
    )
  }
  return fetchMeasures({ curveId, from: range.from, to: range.to, asOf }).then(
    (result): Loaded => ({ kind: 'measure', key: choice.key, result }),
  )
}

/** Not-found, offline and error states (Q4), each with a retry where one helps. */
function FailureMessage({
  result,
  name,
  asOf,
  onRetry,
}: {
  result: Exclude<SeriesResult | MeasuresResult, { kind: 'ok' }>
  name: string
  asOf?: string
  onRetry: () => void
}) {
  if (result.kind === 'not-found') {
    return (
      <Box role="status">
        <EmptyState
          title={asOf ? `No data known as of ${formatUtc(asOf)}` : 'No data known for this selection'}
          description={asOf ? 'Choose Now or a later time in the header.' : `YieldLens has no values for ${name} on this curve yet.`}
        />
      </Box>
    )
  }
  if (result.kind === 'offline') {
    return (
      <Alert color="red" role="alert" title="Backend offline" icon={<IconAlertTriangle size={18} />}>
        <Stack gap="xs" align="flex-start">
          <Text size="sm">The YieldLens API is not reachable.</Text>
          <Button variant="light" size="xs" onClick={onRetry}>
            Try again
          </Button>
        </Stack>
      </Alert>
    )
  }
  return (
    <Alert color="red" role="alert" title={`Could not load ${name}`}>
      <Stack gap="xs" align="flex-start">
        <Text size="sm">{result.detail}</Text>
        <Button variant="light" size="xs" onClick={onRetry}>
          Try again
        </Button>
      </Stack>
    </Alert>
  )
}

export default function SeriesView({ curveId, asOf }: SeriesViewProps) {
  const [selection, setSelection] = useState(DEFAULT_SELECTION)
  const [range, setRange] = useState(() => defaultRange(new Date()))
  const [display, setDisplay] = useState<SeriesDisplay>('chart')
  const [attempt, setAttempt] = useState(0)
  const [loaded, setLoaded] = useState<{ key: string; value: Loaded } | undefined>(undefined)

  useEffect(() => {
    let active = true
    const key = requestKey(selection, range, asOf, attempt)
    loadSelection(selection, curveId, range, asOf).then((value) => {
      if (active) setLoaded({ key, value })
    })
    return () => {
      active = false
    }
  }, [curveId, selection, range, asOf, attempt])

  // Until the answer for the current selection, range and retry arrives, nothing of the old series shows.
  const current = loaded?.key === requestKey(selection, range, asOf, attempt) ? loaded.value : undefined
  const choice = parseChoice(selection)
  const name = choice.kind === 'measure' ? MEASURE_LABEL[choice.key] : `${choice.maturity} yield`
  const retry = () => setAttempt((count) => count + 1)
  const showYield = () => setSelection(DEFAULT_SELECTION)

  const yieldPoints = useMemo(
    () => (current?.kind === 'yield' && current.result.kind === 'ok' ? current.result.series.data.points : []),
    [current],
  )
  const yieldStats = useMemo(() => seriesStats(yieldPoints), [yieldPoints])
  const yieldFlagged = useMemo(() => flaggedCount(yieldPoints), [yieldPoints])
  const hasUnchecked = yieldPoints.some((point) => point.quality.status === 'unchecked')

  const headerActions = (
    <>
      <NativeSelect
        label="Series"
        data={SELECT_DATA}
        value={selection}
        onChange={(event) => setSelection(event.currentTarget.value)}
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

  const toggle = (
    <SegmentedControl
      size="xs"
      value={display}
      onChange={(value) => setDisplay(value as SeriesDisplay)}
      data={[
        { label: 'Chart', value: 'chart' },
        { label: 'Table', value: 'table' },
      ]}
    />
  )

  const subtitle =
    choice.kind === 'measure'
      ? `${MEASURE_LABEL[choice.key]} over valid dates (bp)`
      : `${choice.maturity} yield over valid dates (%)`

  return (
    <Stack component="section" gap="lg">
      <PageHeader title="Time series" subtitle={subtitle} actions={headerActions} />
      {current === undefined && (
        <>
          <SimpleGrid cols={{ base: 2, sm: 4 }}>
            <StatCard label="Last" value={EMPTY} loading />
            <StatCard label="Min" value={EMPTY} loading />
            <StatCard label="Max" value={EMPTY} loading />
            <StatCard label="Change over range" value={EMPTY} loading />
          </SimpleGrid>
          <Skeleton h={320} />
          <VisuallyHidden>Loading…</VisuallyHidden>
        </>
      )}
      {current?.kind === 'yield' && current.result.kind === 'ok' && yieldPoints.length > 0 && (
        <>
          <SimpleGrid cols={{ base: 2, sm: 4 }}>
            <StatCard label="Last" value={yieldStats.last === undefined ? EMPTY : formatYield(yieldStats.last)} />
            <StatCard label="Min" value={yieldStats.min === undefined ? EMPTY : formatYield(yieldStats.min)} />
            <StatCard label="Max" value={yieldStats.max === undefined ? EMPTY : formatYield(yieldStats.max)} />
            <StatCard
              label="Change over range"
              value={yieldStats.changeBp === undefined ? EMPTY : formatBp(yieldStats.changeBp)}
            />
          </SimpleGrid>
          <Card>
            <Group justify="space-between" align="center" wrap="wrap" gap="sm" mb="md">
              <Title order={2}>{current.maturity} yield (%)</Title>
              {toggle}
            </Group>
            {display === 'chart' ? (
              <>
                <SeriesChart rows={seriesChart(yieldPoints)} label="Yield" decimals={3} />
                {yieldFlagged > 0 && (
                  <Stack gap={4} mt="sm">
                    <Text size="sm" c="dimmed">{flaggedCaption(yieldFlagged)}</Text>
                  </Stack>
                )}
              </>
            ) : (
              <DataTable
                columns={[
                  {
                    id: 'valid-date',
                    header: 'Valid date',
                    cell: (point) => point.valid_date,
                    filterText: (point) => point.valid_date,
                  },
                  {
                    id: 'yield',
                    header: 'Yield (%)',
                    align: 'right',
                    cell: (point) => formatYield(point.value),
                    filterText: (point) => formatYield(point.value),
                  },
                  {
                    id: 'quality',
                    header: 'Quality',
                    cell: (point) => <ValueQualityCell quality={point.quality} maturity={current.maturity} />,
                    filterText: (point) => STATUS_LABEL[point.quality.status],
                  },
                ]}
                rows={yieldPoints}
                rowKey={(point) => point.valid_date}
              />
            )}
            {display === 'table' && hasUnchecked && <UncheckedNote />}
          </Card>
        </>
      )}
      {current?.kind === 'yield' && current.result.kind === 'ok' && yieldPoints.length === 0 && (
        <Box role="status">
          <EmptyState
            title="No values in this range"
            description={`There are no ${current.maturity} values from ${range.from} to ${range.to}. Choose a longer range.`}
          />
        </Box>
      )}
      {current?.kind === 'measure' && current.result.kind === 'ok' && (
        current.result.measures.data.points.some((point) => point[current.key] != null) ? (
          <MeasureCard
            points={current.result.measures.data.points}
            measureKey={current.key}
            display={display}
            toggle={toggle}
          />
        ) : (
          <Box role="status">
            <EmptyState
              title="No values in this range"
              description={`${MEASURE_LABEL[current.key]} needs ${measureInputsText(current.key)}; none of the days from ${range.from} to ${range.to} has them. Choose a longer range or another series.`}
            >
              <EmptyState.Actions>
                <Button variant="light" size="xs" onClick={showYield}>
                  Show 10Y yield
                </Button>
              </EmptyState.Actions>
            </EmptyState>
          </Box>
        )
      )}
      {current !== undefined && current.result.kind !== 'ok' && (
        <FailureMessage result={current.result} name={name} asOf={asOf} onRetry={retry} />
      )}
    </Stack>
  )
}
