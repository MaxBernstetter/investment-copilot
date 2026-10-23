import { Anchor, Badge, Box, Group, Popover, SimpleGrid, Stack, Text, Title } from '@mantine/core'
import { METHODOLOGY_URL } from '../config'
import { formatUtc } from '../format'
import { qualityBadgeProps } from '../theme'
import {
  calendarMonths,
  flagLabel,
  ruleLabel,
  sortFindings,
  STATUS_LABEL,
  uncheckedRuleLabels,
  type DayFilter,
  type QualityDay,
} from './qualityData'

const WEEKDAYS = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']

type QualityCalendarProps = {
  days: QualityDay[]
  /** Days with another status are shown as plain numbers. */
  filter: DayFilter
}

/** One block per calendar month, newest first; every business day is a badge that opens its checks. */
export default function QualityCalendar({ days, filter }: QualityCalendarProps) {
  return (
    <Stack gap="lg">
      {calendarMonths(days).map((month) => (
        <Stack key={month.key} gap="xs" component="section" aria-label={month.title}>
          <Title order={3}>{month.title}</Title>
          <SimpleGrid cols={7} spacing="xs" verticalSpacing="xs">
            {WEEKDAYS.map((weekday) => (
              <Text key={weekday} size="xs" c="dimmed" ta="center">
                {weekday}
              </Text>
            ))}
            {Array.from({ length: month.leading }, (_, index) => (
              <Box key={`blank-${index}`} aria-hidden />
            ))}
            {month.cells.map(({ date, day, quality }) =>
              quality !== undefined && (filter === 'all' || quality.status === filter) ? (
                <Group key={date} justify="center">
                  <DayBadge day={quality} number={day} />
                </Group>
              ) : (
                <Text key={date} size="sm" c="dimmed" ta="center">
                  {day}
                </Text>
              ),
            )}
          </SimpleGrid>
        </Stack>
      ))}
    </Stack>
  )
}

function DayBadge({ day, number }: { day: QualityDay; number: number }) {
  const notChecked = uncheckedRuleLabels(day)
  return (
    <Popover width={320} withArrow position="bottom" trapFocus returnFocus>
      <Popover.Target>
        <Badge
          component="button"
          type="button"
          size="lg"
          miw={64}
          {...qualityBadgeProps(day.status)}
          aria-label={`${day.valid_date}, ${STATUS_LABEL[day.status]}`}
        >
          {number}
        </Badge>
      </Popover.Target>
      <Popover.Dropdown>
        <Stack gap="xs">
          <Text fw={600}>{day.valid_date}</Text>
          <Group gap="xs">
            <Badge {...qualityBadgeProps(day.status)}>{STATUS_LABEL[day.status]}</Badge>
            {day.checked_as_of && (
              <Text size="sm" c="dimmed">
                Checked as of {formatUtc(day.checked_as_of)}
              </Text>
            )}
          </Group>
          {day.status === 'unchecked' && (
            <Text size="sm">
              No check result is known for this day at this knowledge time. Checks run after each data load (the
              daily load in Airflow); they cannot be started from this page. A day that is not published yet stays
              unchecked until the next load.
            </Text>
          )}
          {sortFindings(day.findings).map((finding, index) => (
            <Stack key={index} gap={4}>
              <Group gap="xs">
                <Badge {...qualityBadgeProps(finding.severity)}>{flagLabel(finding)}</Badge>
                {finding.maturity && <Text size="sm">{ruleLabel(finding.rule)} at {finding.maturity}</Text>}
              </Group>
              <Text size="sm">{finding.explanation}</Text>
              <Text size="sm" c="dimmed">
                {finding.evidence}
              </Text>
            </Stack>
          ))}
          {notChecked.length > 0 && (
            <Text size="sm" c="dimmed">
              Not checked: {notChecked.join(', ')}
            </Text>
          )}
          <Anchor size="sm" href={METHODOLOGY_URL} target="_blank" rel="noreferrer">
            How we check this
          </Anchor>
        </Stack>
      </Popover.Dropdown>
    </Popover>
  )
}
