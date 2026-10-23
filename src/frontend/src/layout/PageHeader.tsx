import type { ReactNode } from 'react'
import { Group, Stack, Text, Title } from '@mantine/core'

type PageHeaderProps = {
  title: string
  subtitle?: ReactNode
  /** Page actions, aligned right and wrapping below the title on narrow screens. */
  actions?: ReactNode
}

/** The title of a page (the only h1 on it), with an optional one-line subtitle and actions. */
export default function PageHeader({ title, subtitle, actions }: PageHeaderProps) {
  return (
    <Group justify="space-between" align="flex-start" gap="md">
      <Stack gap={4}>
        <Title order={1}>{title}</Title>
        {subtitle && (
          <Text size="sm" c="dimmed">
            {subtitle}
          </Text>
        )}
      </Stack>
      {actions && <Group gap="sm" align="flex-end">{actions}</Group>}
    </Group>
  )
}
