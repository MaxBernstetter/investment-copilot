import type { ReactNode } from 'react'
import { ActionIcon, Card, Group, rem, Skeleton, Stack, Text, Tooltip } from '@mantine/core'
import { IconInfoCircle } from '@tabler/icons-react'

type StatCardProps = {
  label: string
  value: string
  hint?: string
  /** Definition in a tooltip on an info icon next to the label (Q5). */
  help?: string
  /** Shown right of the value, e.g. the "Inverted" badge. */
  badge?: ReactNode
  /** Shows a skeleton in place of the value and hides the hint and badge. */
  loading?: boolean
}

/**
 * One key figure: uppercase label, tabular value, optional help, badge and dimmed hint.
 * The label and value rows are plain text unless help or a badge adds a control beside them.
 */
export default function StatCard({ label, value, hint, help, badge, loading = false }: StatCardProps) {
  const labelText = (
    <Text size="xs" c="dimmed" tt="uppercase">
      {label}
    </Text>
  )
  const valueText = (
    <Text variant="tabular" fw={600} fz={rem(15)} lh={1.4}>
      {value}
    </Text>
  )
  return (
    <Card>
      <Stack gap={4}>
        {help === undefined ? (
          labelText
        ) : (
          <Group gap={4} wrap="nowrap" align="center">
            {labelText}
            <Tooltip label={help}>
              <ActionIcon variant="subtle" size="sm" aria-label={`About ${label}`}>
                <IconInfoCircle size={16} aria-hidden />
              </ActionIcon>
            </Tooltip>
          </Group>
        )}
        {loading ? (
          <Skeleton h={21} w={88} />
        ) : badge === undefined ? (
          valueText
        ) : (
          <Group justify="space-between" wrap="nowrap" gap="xs">
            {valueText}
            {badge}
          </Group>
        )}
        {!loading && hint !== undefined && (
          <Text size="xs" c="dimmed">
            {hint}
          </Text>
        )}
      </Stack>
    </Card>
  )
}
