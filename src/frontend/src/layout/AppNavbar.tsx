import { NavLink, Stack } from '@mantine/core'
import { CurveSwitch, VIEWS } from './AppHeader'

type AppNavbarProps = {
  view: string | null
  onViewChange: (view: string) => void
  curveId: string
  onCurveChange: (id: string) => void
  /** Called after a choice, so the navbar closes on small screens. */
  onNavigate: () => void
}

/** Views and curve choice for small screens, shown in the navbar opened by the Burger. */
export default function AppNavbar({ view, onViewChange, curveId, onCurveChange, onNavigate }: AppNavbarProps) {
  return (
    <Stack gap="md">
      <Stack gap={4}>
        {VIEWS.map((item) => {
          const active = view === item.value
          return (
            <NavLink
              key={item.value}
              component="button"
              label={item.label}
              active={active}
              aria-current={active ? 'page' : undefined}
              onClick={() => {
                onViewChange(item.value)
                onNavigate()
              }}
            />
          )
        })}
      </Stack>
      <CurveSwitch value={curveId} onChange={onCurveChange} fullWidth />
    </Stack>
  )
}
