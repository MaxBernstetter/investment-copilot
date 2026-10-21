import { useEffect, useState } from 'react'
import { AppShell, Alert, Button, Container, Skeleton, Stack, Tabs, Text, VisuallyHidden } from '@mantine/core'
import { useDisclosure } from '@mantine/hooks'
import { IconAlertTriangle, IconInfoCircle } from '@tabler/icons-react'
import { isBackendOnline } from './backend'
import { readAsOf, writeAsOf } from './asOf'
import ChangesView from './changes/ChangesView'
import AppFooter from './layout/AppFooter'
import AppHeader from './layout/AppHeader'
import AppNavbar from './layout/AppNavbar'
import PageHeader from './layout/PageHeader'
import CurveView from './curve/CurveView'
import { curveById, readCurveId, writeCurveId } from './curve/curves'
import SeriesView from './series/SeriesView'
import QualityView from './quality/QualityView'

type BackendState = 'checking' | 'online' | 'offline'

export default function App() {
  const [state, setState] = useState<BackendState>('checking')
  const [attempt, setAttempt] = useState(0)
  const [view, setView] = useState<string | null>('curve')
  const [curveId, setCurveId] = useState(() => readCurveId(window.location.search))
  const [asOf, setAsOf] = useState<string | undefined>(() => readAsOf(window.location.search))
  const [navOpened, navHandlers] = useDisclosure(false)
  const simulated = curveById(curveId).isSimulated
  const online = state === 'online'

  const changeCurve = (next: string) => {
    setCurveId(next)
    writeCurveId(next)
  }

  const changeAsOf = (next: string | undefined) => {
    setAsOf(next)
    writeAsOf(next)
  }

  useEffect(() => {
    let active = true
    isBackendOnline().then((isOnline) => {
      if (active) setState(isOnline ? 'online' : 'offline')
    })
    return () => {
      active = false
    }
  }, [attempt])

  const retry = () => {
    setState('checking')
    setAttempt((count) => count + 1)
  }

  return (
    <Tabs value={view} onChange={setView}>
      <AppShell
        header={{ height: 56 }}
        navbar={
          online
            ? { width: 260, breakpoint: 'sm', collapsed: { desktop: true, mobile: !navOpened } }
            : undefined
        }
        padding={0}
      >
        <AppShell.Header>
          <AppHeader
            online={online}
            curveId={curveId}
            onCurveChange={changeCurve}
            simulated={simulated}
            asOf={asOf}
            onAsOfChange={changeAsOf}
            navOpened={navOpened}
            onToggleNav={navHandlers.toggle}
          />
        </AppShell.Header>
        {online && (
          <AppShell.Navbar p="md" hiddenFrom="sm" aria-label="Views">
            {navOpened && (
              <AppNavbar
                view={view}
                onViewChange={setView}
                curveId={curveId}
                onCurveChange={changeCurve}
                onNavigate={navHandlers.close}
              />
            )}
          </AppShell.Navbar>
        )}
        <AppShell.Main>
          <Container size={1200} px={{ base: 'md', sm: 'lg' }} py="lg">
            {state === 'checking' && (
              <Stack gap="lg">
                <PageHeader title="Connecting" />
                <Skeleton h={320} />
                <VisuallyHidden>Loading…</VisuallyHidden>
              </Stack>
            )}
            {state === 'offline' && (
              <Stack gap="lg">
                <PageHeader title="Service unavailable" />
                <Alert color="red" role="alert" title="Backend offline" icon={<IconAlertTriangle size={18} />}>
                  <Stack gap="xs" align="flex-start">
                    <Text size="sm">The YieldLens API is not reachable. Try again in a moment.</Text>
                    <Button variant="light" size="xs" onClick={retry}>
                      Try again
                    </Button>
                  </Stack>
                </Alert>
              </Stack>
            )}
            {online && (
              <Stack gap="lg">
                {simulated && (
                  <Alert color="orange" role="note" py="xs" icon={<IconInfoCircle size={18} />}>
                    Simulated scenario data, not an ECB publication.
                  </Alert>
                )}
                <Tabs.Panel value="curve">
                  <CurveView key={curveId} curveId={curveId} asOf={asOf} />
                </Tabs.Panel>
                <Tabs.Panel value="series">
                  <SeriesView key={curveId} curveId={curveId} asOf={asOf} />
                </Tabs.Panel>
                <Tabs.Panel value="changes">
                  <ChangesView key={curveId} curveId={curveId} asOf={asOf} />
                </Tabs.Panel>
                <Tabs.Panel value="quality">
                  <QualityView key={curveId} curveId={curveId} asOf={asOf} />
                </Tabs.Panel>
              </Stack>
            )}
          </Container>
        </AppShell.Main>
        <AppFooter simulated={simulated} />
      </AppShell>
    </Tabs>
  )
}
