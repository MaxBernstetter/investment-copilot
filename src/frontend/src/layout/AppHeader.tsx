import {
  Badge,
  Box,
  ActionIcon,
  Burger,
  Group,
  SegmentedControl,
  Tabs,
  Text,
  Tooltip,
  useComputedColorScheme,
  useMantineColorScheme,
} from '@mantine/core'
import { IconMoon, IconSun } from '@tabler/icons-react'
import { CURVES } from '../curve/curves'
import AsOfStatus from './AsOfStatus'

/** The views, in tab order. The navbar on small screens lists the same views. */
export const VIEWS = [
  { value: 'curve', label: 'Curve' },
  { value: 'series', label: 'Time series' },
  { value: 'changes', label: 'Changes' },
] as const

const CURVE_OPTIONS = CURVES.map((curve) => ({
  label: curve.isSimulated ? 'Simulated' : 'Real',
  value: curve.id,
}))

type CurveSwitchProps = {
  value: string
  onChange: (id: string) => void
  fullWidth?: boolean
}

/** The Real / Simulated choice; the same control appears in the header and in the navbar. */
export function CurveSwitch({ value, onChange, fullWidth }: CurveSwitchProps) {
  return (
    <SegmentedControl
      aria-label="Curve"
      size="xs"
      fullWidth={fullWidth}
      value={value}
      onChange={onChange}
      data={CURVE_OPTIONS}
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
        {computed === 'dark' ? <IconSun size={18} /> : <IconMoon size={18} />}
      </ActionIcon>
    </Tooltip>
  )
}

type AppHeaderProps = {
  /** Navigation and the curve choice exist only once the backend is reachable. */
  online: boolean
  curveId: string
  onCurveChange: (id: string) => void
  simulated: boolean
  asOf: string | undefined
  onAsOfChange: (asOf: string | undefined) => void
  navOpened: boolean
  onToggleNav: () => void
}

export default function AppHeader({
  online,
  curveId,
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
        {online && <Burger
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
      {online && (
        <Box component="nav" visibleFrom="sm" aria-label="Views">
          <Tabs.List>
            {VIEWS.map((item) => (
              <Tabs.Tab key={item.value} value={item.value}>
                {item.label}
              </Tabs.Tab>
            ))}
          </Tabs.List>
        </Box>
      )}
      <Group gap="sm" wrap="nowrap">
        {online && (
          <Box visibleFrom="sm">
            <CurveSwitch value={curveId} onChange={onCurveChange} />
          </Box>
        )}
        {online && simulated && (
          <Badge color="orange.6" variant="filled">
            Simulated
          </Badge>
        )}
        {online && <AsOfStatus asOf={asOf} onChange={onAsOfChange} />}
        <ColorSchemeToggle />
      </Group>
    </Group>
  )
}
