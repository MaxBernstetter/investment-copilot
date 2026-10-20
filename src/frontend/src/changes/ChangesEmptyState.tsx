import { Stack, Text } from '@mantine/core'

type ChangesEmptyStateProps = {
  title: string
  description: string
}

/** Shown before the user picks the earlier knowledge time to compare. */
export default function ChangesEmptyState({ title, description }: ChangesEmptyStateProps) {
  return (
    <Stack gap="xs" role="status">
      <Text fw={600}>{title}</Text>
      <Text c="dimmed">{description}</Text>
    </Stack>
  )
}
