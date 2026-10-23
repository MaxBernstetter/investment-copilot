import type { ReactNode } from 'react'
import { ActionIcon, Card, Group, SimpleGrid, Stack, Text, Title, Tooltip } from '@mantine/core'
import { IconInfoCircle } from '@tabler/icons-react'
import StatCard from '../components/StatCard'
import { MEASURE_HELP, MEASURE_LABEL, type MeasureKey, type MeasurePoint } from '../curve/measuresData'
import { EMPTY, formatBp } from '../format'
import MeasureTable from './MeasureTable'
import SeriesChart from './SeriesChart'
import { flaggedMeasureDays, gapDays, lastValueDate, measureRows, measureStats } from './measureSeries'
import { flaggedCaption } from './seriesData'

function gapCaption(count: number): string {
  return `No value on ${count} ${count === 1 ? 'day' : 'days'}; shown as gaps.`
}

type MeasureCardProps = {
  points: MeasurePoint[]
  measureKey: MeasureKey
  display: 'chart' | 'table'
  /** The Chart | Table control, shared with the yield card. */
  toggle: ReactNode
}

/** Key figures, the bp chart or table, and the captions for one measure (#258 MR2). */
export default function MeasureCard({ points, measureKey, display, toggle }: MeasureCardProps) {
  const label = MEASURE_LABEL[measureKey]
  const stats = measureStats(points, measureKey)
  const lastDate = lastValueDate(points, measureKey)
  const lastRowDate = points[points.length - 1]?.valid_date
  const gaps = gapDays(points, measureKey)
  const flagged = flaggedMeasureDays(points, measureKey)

  const captions = [
    gaps > 0 ? gapCaption(gaps) : undefined,
    flagged > 0 ? flaggedCaption(flagged) : undefined,
  ].filter((caption): caption is string => caption !== undefined)

  return (
    <>
      <SimpleGrid cols={{ base: 2, sm: 4 }}>
        <StatCard
          label="Last"
          value={stats.last === undefined ? EMPTY : formatBp(stats.last)}
          hint={lastDate !== undefined && lastDate !== lastRowDate ? `On ${lastDate}` : undefined}
        />
        <StatCard label="Min" value={stats.min === undefined ? EMPTY : formatBp(stats.min)} />
        <StatCard label="Max" value={stats.max === undefined ? EMPTY : formatBp(stats.max)} />
        <StatCard
          label="Change over range"
          value={stats.changeBp === undefined ? EMPTY : formatBp(stats.changeBp)}
          hint={stats.changeBp === undefined ? 'Needs two values' : undefined}
        />
      </SimpleGrid>
      <Card>
        <Group justify="space-between" align="center" wrap="wrap" gap="sm" mb="md">
          <Group gap={8} wrap="nowrap" align="center">
            <Title order={2}>{label} (bp)</Title>
            <Tooltip label={MEASURE_HELP[measureKey]}>
              <ActionIcon variant="subtle" size="sm" aria-label={`About ${label}`}>
                <IconInfoCircle size={16} aria-hidden />
              </ActionIcon>
            </Tooltip>
          </Group>
          {toggle}
        </Group>
        {display === 'chart' ? (
          <SeriesChart rows={measureRows(points, measureKey)} label={label} decimals={1} />
        ) : (
          <MeasureTable points={points} measureKey={measureKey} />
        )}
        {captions.length > 0 && (
          <Stack gap={4} mt="sm">
            {captions.map((caption) => (
              <Text key={caption} size="sm" c="dimmed">
                {caption}
              </Text>
            ))}
          </Stack>
        )}
      </Card>
    </>
  )
}
