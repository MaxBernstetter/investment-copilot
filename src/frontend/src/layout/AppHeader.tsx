import {
  Badge,
  Box,
  ActionIcon,
  Burger,
  Group,
  Select,
  Tabs,
  Text,
  Tooltip,
  useComputedColorScheme,
  useMantineColorScheme,
} from '@mantine/core'
import { IconMoon, IconSun } from '@tabler/icons-react'
import type { CurveInfo } from '../curve/fetchCurves'
import { curveSelectData } from '../curve/curves'
import AsOfStatus from './AsOfStatus'

/** The views, in tab order. The navbar on small screens lists the same views. */
export const VIEWS = [
  {
    value: 'curve',
    label: 'Curve',
    help: 'Yields across all maturities on one valid date. Pick a date, overlay other dates or curves, and read the key figures.',
  },
  {
    value: 'series',
    label: 'Time series',
    help: 'How one maturity, spread or curvature moves over a date range, as a chart and a table.',
  },
  {
    value: 'changes',
    label: 'Changes',
    help: 'What changed in the data between two knowledge times: corrections and late values, per value.',
  },
  {
    value: 'quality',
    label: 'Quality',
    help: 'Plausibility and completeness checks per business day. See warnings, what was not checked, and when.',
  },
] as const

type CurveSelectProps = {
  value: string
  onChange: (id: string) => void
  catalogue: readonly CurveInfo[]
  fullWidth?: boolean
}

/** The curve choice; the same control appears in the header and in the navbar. */
export function CurveSelect({ value, onChange, catalogue, fullWidth }: CurveSelectProps) {
  return (
    <Select
      aria-label="Curve"
      size="xs"
      w={fullWidth ? '100%' : 280}
      allowDeselect={false}
      checkIconPosition="right"
      comboboxProps={{ width: 'max-content', position: 'bottom-end' }}
      data={curveSelectData(catalogue)}
      value={value}
      onChange={(id) => {
        if (id !== null) onChange(id)
      }}
    />
  )
}

function ColorSchemeToggle() {
  const { setColorScheme } = useMantineColorScheme()
  const computed = useComputedColorScheme('light')
  const next = computed === 'dark' ? 'light' : 'dark'
  return (
    <Tooltip label={next === 'dark' ? 'Dark colours' : 'Light colours'}>
      <ActionIcon variant="default" size="lg" aria-label="Toggle colour scheme" onClick={() => setColorScheme(next)}>
        {/* The icon shows the current scheme; the span stays mounted so only its child swaps. */}
        <Box component="span" display="flex">
          {computed === 'dark' ? <IconMoon size={18} /> : <IconSun size={18} />}
        </Box>
      </ActionIcon>
    </Tooltip>
  )
}

type AppHeaderProps = {
  /** Navigation and the curve choice exist only once the backend is reachable and the curve is known. */
  ready: boolean
  curveId: string
  catalogue: readonly CurveInfo[]
  onCurveChange: (id: string) => void
  simulated: boolean
  asOf: string | undefined
  onAsOfChange: (asOf: string | undefined) => void
  navOpened: boolean
  onToggleNav: () => void
}

export default function AppHeader({
  ready,
  curveId,
  catalogue,
  onCurveChange,
  simulated,
  asOf,
  onAsOfChange,
  navOpened,
  onToggleNav,
}: AppHeaderProps) {
  return (
    <Group h="100%" px="md" justify="space-between" wrap="nowrap" gap="sm">
      <Group gap="sm" wrap="nowrap">
        {ready && <Burger
            opened={navOpened}
            onClick={onToggleNav}
            hiddenFrom="sm"
            size="sm"
            aria-label="Toggle navigation"
            aria-expanded={navOpened}
          />}
        <Text fw={700} size="lg">
          YieldLens
        </Text>
      </Group>
      {ready && (
        <Box component="nav" visibleFrom="sm" aria-label="Views">
          <Tabs.List>
            {VIEWS.map((item) => (
              <Tooltip key={item.value} label={item.help} multiline w={280} openDelay={300}>
                <Tabs.Tab value={item.value}>{item.label}</Tabs.Tab>
              </Tooltip>
            ))}
          </Tabs.List>
        </Box>
      )}
      <Group gap="sm" wrap="nowrap">
        {ready && (
          <Box visibleFrom="sm">
            <CurveSelect value={curveId} onChange={onCurveChange} catalogue={catalogue} />
          </Box>
        )}
        {ready && simulated && (
          <Badge color="orange.6" variant="filled">
            Simulated
          </Badge>
        )}
        {ready && <AsOfStatus asOf={asOf} onChange={onAsOfChange} />}
        <ColorSchemeToggle />
      </Group>
    </Group>
  )
}
