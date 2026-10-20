import { Card, rem, Stack, Text } from '@mantine/core'

type StatCardProps = {
  label: string
  value: string
  hint?: string
}

/** One key figure: uppercase label, tabular value, optional dimmed hint. */
export default function StatCard({ label, value, hint }: StatCardProps) {
  return (
    <Card>
      <Stack gap={4}>
        <Text size="xs" c="dimmed" tt="uppercase">
          {label}
        </Text>
        <Text fw={600} fz={rem(15)} lh={1.4} style={{ fontVariantNumeric: 'tabular-nums' }}>
          {value}
        </Text>
        {hint !== undefined && (
          <Text size="xs" c="dimmed">
            {hint}
          </Text>
        )}
      </Stack>
    </Card>
  )
}
