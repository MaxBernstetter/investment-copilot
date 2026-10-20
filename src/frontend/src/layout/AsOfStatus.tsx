import { Box, Button, Popover, Stack, Text } from '@mantine/core'
import { IconClock } from '@tabler/icons-react'
import AsOfControl from '../curve/AsOfControl'
import { formatUtc } from '../format'

type AsOfStatusProps = {
  /** The knowledge time (UTC ISO string), or undefined for the latest knowledge. */
  asOf: string | undefined
  onChange: (asOf: string | undefined) => void
}

/**
 * The knowledge time shared by all views: a status button in the header that opens the choice.
 * Below `sm` the header has no room for the full date, so the button shows the clock time only;
 * its accessible name always has the full label.
 */
export default function AsOfStatus({ asOf, onChange }: AsOfStatusProps) {
  const label = asOf ? `As of ${formatUtc(asOf, 'minutes')}` : 'Live'
  const [, clock] = asOf ? formatUtc(asOf, 'minutes').split(', ') : []
  return (
    <Box role="status">
      <Popover width={320} position="bottom-end" withArrow shadow="md" trapFocus returnFocus>
        <Popover.Target>
          <Button
            aria-label={label}
            variant={asOf ? 'filled' : 'light'}
            color={asOf ? 'yellow' : 'blue'}
            autoContrast={asOf !== undefined}
            size="xs"
            leftSection={<IconClock size={14} />}
          >
            {asOf ? (
              <>
                <Text component="span" hiddenFrom="sm">
                  {clock}
                </Text>
                <Text component="span" visibleFrom="sm">
                  {label}
                </Text>
              </>
            ) : (
              'Live'
            )}
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
