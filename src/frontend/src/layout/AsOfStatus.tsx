import { Box, Button, Popover, Stack, Text } from '@mantine/core'
import { IconClock } from '@tabler/icons-react'
import AsOfControl from '../curve/AsOfControl'
import { formatUtc } from '../format'

type AsOfStatusProps = {
  /** The knowledge time (UTC ISO string), or undefined for the latest knowledge. */
  asOf: string | undefined
  onChange: (asOf: string | undefined) => void
}

/** The knowledge time shared by all views: a header status button that opens the choice. */
export default function AsOfStatus({ asOf, onChange }: AsOfStatusProps) {
  const label = asOf ? `As of ${formatUtc(asOf, 'minutes')}` : 'Live'
  return (
    <Box role="status">
      <Popover width={320} position="bottom-end" withArrow shadow="md" trapFocus returnFocus>
        <Popover.Target>
          <Button
            variant={asOf ? 'filled' : 'light'}
            color={asOf ? 'yellow' : 'blue'}
            autoContrast={asOf !== undefined}
            size="xs"
            leftSection={<IconClock size={14} />}
          >
            {label}
          </Button>
        </Popover.Target>
        <Popover.Dropdown>
          <Stack gap="sm">
            <AsOfControl asOf={asOf} onChange={onChange} />
            <Text size="xs" c="dimmed">
              See the data exactly as YieldLens knew it at that moment. Later corrections are hidden. Choose Now to
              see the latest knowledge.
            </Text>
          </Stack>
        </Popover.Dropdown>
      </Popover>
    </Box>
  )
}
