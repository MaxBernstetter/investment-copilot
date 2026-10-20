import { Stack, Text, Title } from '@mantine/core'

type ChangesEmptyStateProps = {
  title: string
  description: string
}

/** Shown before the user picks the earlier knowledge time to compare. */
export default function ChangesEmptyState({ title, description }: ChangesEmptyStateProps) {
  return (
    <Stack gap="xs" role="status">
      <Title order={3}>{title}</Title>
      <Text c="dimmed">{description}</Text>
    </Stack>
  )
}
