import { useEffect, useState } from 'react'
import {
  Alert,
  Badge,
  Box,
  Button,
  Card,
  EmptyState,
  Group,
  SegmentedControl,
  SimpleGrid,
  Skeleton,
  Stack,
  Table,
  Text,
  TextInput,
  Title,
  VisuallyHidden,
} from '@mantine/core'
import { IconAlertTriangle } from '@tabler/icons-react'
import StatCard from '../components/StatCard'
import type { CurveInfo } from '../curve/fetchCurves'
import { formatUtc } from '../format'
import PageHeader from '../layout/PageHeader'
import { qualityBadgeProps } from '../theme'
import { fetchQuality, type QualityResult } from './fetchQuality'
import HowWeCheck from './HowWeCheck'
import QualityFlag from './QualityFlag'
import {
  defaultQualityRange,
  filterDays,
  newestFirst,
  qualityStats,
  rangeError,
  sortFindings,
  STATUS_LABEL,
  uncheckedRuleLabels,
  type DayFilter,
  type QualityDay,
} from './qualityData'

const EMPTY = '–'

type QualityViewProps = {
  curve: CurveInfo
  /** The knowledge time shared by all views, set in the header. */
  asOf?: string
}

export default function QualityView({ curve, asOf }: QualityViewProps) {
  const [range, setRange] = useState(() => defaultQualityRange(new Date()))
  const [filter, setFilter] = useState<DayFilter>('all')
  const [result, setResult] = useState<QualityResult | undefined>(undefined)
  const [attempt, setAttempt] = useState(0)

  const error = rangeError(range)

  useEffect(() => {
    if (error) return
    let active = true
    fetchQuality({ curveId: curve.id, from: range.from, to: range.to, asOf }).then((next) => {
      if (active) setResult(next)
    })
    return () => {
      active = false
    }
  }, [curve.id, range.from, range.to, asOf, attempt, error])

  const retry = () => {
    setResult(undefined)
    setAttempt((count) => count + 1)
  }

  // Bumping attempt as well as clearing the result refetches even when the range is already the default.
  const resetRange = () => {
    setRange(defaultQualityRange(new Date()))
    setFilter('all')
    setResult(undefined)
    setAttempt((count) => count + 1)
  }

  const headerActions = (
    <>
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
        error={error}
        onChange={(event) => {
          if (event.currentTarget.value) setRange({ ...range, to: event.currentTarget.value })
        }}
      />
    </>
  )

  const ok = result?.kind === 'ok' ? result.quality.data : undefined
  const days = ok?.days ?? []

  return (
    <Stack component="section" gap="lg">
      <PageHeader
        title="Data quality"
        subtitle={`Plausibility and completeness checks per business day, ${curve.label}`}
        actions={headerActions}
      />
      {error === undefined && result === undefined && (
        <>
          <SimpleGrid cols={4}>
            <Skeleton h={104} />
            <Skeleton h={104} />
            <Skeleton h={104} />
            <Skeleton h={104} />
          </SimpleGrid>
          <Skeleton h={180} />
          <VisuallyHidden>Loading…</VisuallyHidden>
        </>
      )}
      {error === undefined && ok !== undefined && days.length === 0 && (
        <Box role="status">
          <EmptyState
            title="No business days in this range"
            description="Choose a range that includes at least one TARGET business day."
          >
            <EmptyState.Actions>
              <Button variant="light" size="xs" onClick={resetRange}>
                Show last 30 days
              </Button>
            </EmptyState.Actions>
          </EmptyState>
        </Box>
      )}
      {error === undefined && ok !== undefined && days.length > 0 && (
        <QualityDays days={days} filter={filter} onFilterChange={setFilter} />
      )}
      {error === undefined && result?.kind === 'not-found' && (
        <Box role="status">
          <EmptyState
            title="No quality results for this curve"
            description="Quality checks have not run for this curve yet."
          >
            <EmptyState.Actions>
              <Button variant="light" size="xs" onClick={resetRange}>
                Show last 30 days
              </Button>
            </EmptyState.Actions>
          </EmptyState>
        </Box>
      )}
      {error === undefined && result?.kind === 'offline' && (
        <Alert color="red" role="alert" title="Backend offline" icon={<IconAlertTriangle size={18} />}>
          <Stack gap="xs" align="flex-start">
            <Text size="sm">The YieldLens API is not reachable. Try again in a moment.</Text>
            <Button variant="light" size="xs" onClick={retry}>
              Try again
            </Button>
          </Stack>
        </Alert>
      )}
      {error === undefined && (result?.kind === 'invalid' || result?.kind === 'error') && (
        <Alert color="red" role="alert" title="Could not load quality results">
          <Stack gap="xs" align="flex-start">
            <Text size="sm">{result.detail}</Text>
            <Button variant="light" size="xs" onClick={retry}>
              Try again
            </Button>
          </Stack>
        </Alert>
      )}
      <HowWeCheck />
    </Stack>
  )
}

type QualityDaysProps = {
  days: QualityDay[]
  filter: DayFilter
  onFilterChange: (filter: DayFilter) => void
}

function QualityDays({ days, filter, onFilterChange }: QualityDaysProps) {
  const stats = qualityStats(days)
  const shown = filterDays(newestFirst(days), filter)

  return (
    <>
      <SimpleGrid cols={4}>
        <StatCard label="Days checked" value={String(stats.checked)} hint={`of ${stats.total} business days`} />
        <StatCard label="Warnings" value={String(stats.warnings)} hint={`on ${stats.warnDays} days`} />
        <StatCard label="Info flags" value={String(stats.infos)} hint={`on ${stats.infoDays} days`} />
        <StatCard
          label="Last check"
          value={stats.lastCheck === undefined ? EMPTY : formatUtc(stats.lastCheck)}
          hint={stats.lastCheck === undefined ? 'No check results known at this time' : undefined}
        />
      </SimpleGrid>
      <Card>
        <Stack gap="md">
          <Group justify="space-between" align="center" wrap="wrap" gap="sm">
            <Title order={2}>Checks per day</Title>
            <SegmentedControl
              size="xs"
              aria-label="Show days"
              value={filter}
              onChange={(value) => onFilterChange(value as DayFilter)}
              data={[
                { label: 'All', value: 'all' },
                { label: 'Warn', value: 'warn' },
                { label: 'Info', value: 'info' },
                { label: 'Unchecked', value: 'unchecked' },
              ]}
            />
          </Group>
          {shown.length === 0 ? (
            <Box role="status">
              <EmptyState
                title="No days match this filter"
                description="Every day in this range has a different status."
              >
                <EmptyState.Actions>
                  <Button variant="light" size="xs" onClick={() => onFilterChange('all')}>
                    Show all days
                  </Button>
                </EmptyState.Actions>
              </EmptyState>
            </Box>
          ) : (
            <Table.ScrollContainer minWidth={720}>
              <Table striped>
                <Table.Thead>
                  <Table.Tr>
                    <Table.Th scope="col">Valid date</Table.Th>
                    <Table.Th scope="col">Status</Table.Th>
                    <Table.Th scope="col">Findings</Table.Th>
                    <Table.Th scope="col">Checked as of</Table.Th>
                  </Table.Tr>
                </Table.Thead>
                <Table.Tbody>
                  {shown.map((day) => {
                    const notChecked = uncheckedRuleLabels(day)
                    return (
                      <Table.Tr key={day.valid_date}>
                        <Table.Td>{day.valid_date}</Table.Td>
                        <Table.Td>
                          <Badge {...qualityBadgeProps(day.status)}>{STATUS_LABEL[day.status]}</Badge>
                        </Table.Td>
                        <Table.Td>
                          <Stack gap={4}>
                            {day.findings.length > 0 ? (
                              <Group gap={4} wrap="wrap">
                                {sortFindings(day.findings).map((finding, index) => (
                                  <QualityFlag key={index} finding={finding} />
                                ))}
                              </Group>
                            ) : (
                              <Text>{EMPTY}</Text>
                            )}
                            {notChecked.length > 0 && (
                              <Text size="xs" c="dimmed">
                                Not checked: {notChecked.join(', ')}
                              </Text>
                            )}
                          </Stack>
                        </Table.Td>
                        <Table.Td>{day.checked_as_of ? formatUtc(day.checked_as_of) : EMPTY}</Table.Td>
                      </Table.Tr>
                    )
                  })}
                </Table.Tbody>
              </Table>
            </Table.ScrollContainer>
          )}
        </Stack>
      </Card>
    </>
  )
}
