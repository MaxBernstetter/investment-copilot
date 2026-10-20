import { Card, Stack, Text, Title } from '@mantine/core'

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
        <Title order={3}>{value}</Title>
        {hint !== undefined && (
          <Text size="xs" c="dimmed">
            {hint}
          </Text>
        )}
      </Stack>
    </Card>
  )
}
