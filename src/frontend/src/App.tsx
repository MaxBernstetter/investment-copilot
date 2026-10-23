import { useEffect, useState } from 'react'
import { AppShell, Alert, Box, Button, Container, EmptyState, Skeleton, Stack, Tabs, Text, VisuallyHidden } from '@mantine/core'
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
import { readCurveId, resolveCurve, writeCurveId } from './curve/curves'
import { fetchCurves, type CurvesResult } from './curve/fetchCurves'
import { useOverlay } from './curve/useOverlay'
import { sourceOf } from './curve/sources'
import SeriesView from './series/SeriesView'
import QualityView from './quality/QualityView'

type BackendState = 'checking' | 'online' | 'offline'
type CatalogueState = { kind: 'loading' } | CurvesResult

export default function App() {
  const [state, setState] = useState<BackendState>('checking')
  const [attempt, setAttempt] = useState(0)
  const [catalogueAttempt, setCatalogueAttempt] = useState(0)
  const [view, setView] = useState<string | null>('curve')
  const [catalogue, setCatalogue] = useState<CatalogueState>({ kind: 'loading' })
  const [curveId, setCurveId] = useState(() => readCurveId(window.location.search))
  const [asOf, setAsOf] = useState<string | undefined>(() => readAsOf(window.location.search))
  const [navOpened, navHandlers] = useDisclosure(false)
  const curves = catalogue.kind === 'ok' ? catalogue.curves : []
  const curve = resolveCurve(curves, curveId)
  const overlay = useOverlay(curves)
  const ready = state === 'online' && curve !== undefined
  const simulated = curve?.simulated ?? false

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

  useEffect(() => {
    if (state !== 'online') return
    let active = true
    fetchCurves().then((next) => {
      if (active) setCatalogue(next)
    })
    return () => {
      active = false
    }
  }, [state, catalogueAttempt])

  useEffect(() => {
    if (curve && curve.id !== readCurveId(window.location.search)) writeCurveId(curve.id)
  }, [curve])

  const retry = () => {
    setState('checking')
    setCatalogue({ kind: 'loading' })
    setAttempt((count) => count + 1)
  }

  /** Refetches only the curve list; the health check is already passed. */
  const retryCatalogue = () => {
    setCatalogue({ kind: 'loading' })
    setCatalogueAttempt((count) => count + 1)
  }

  return (
    <Tabs value={view} onChange={setView}>
      <AppShell
        header={{ height: 56 }}
        navbar={
          ready
            ? { width: 260, breakpoint: 'sm', collapsed: { desktop: true, mobile: !navOpened } }
            : undefined
        }
        padding={0}
      >
        <AppShell.Header>
          <AppHeader
            ready={ready}
            curveId={curve?.id ?? curveId}
            catalogue={curves}
            onCurveChange={changeCurve}
            simulated={simulated}
            asOf={asOf}
            onAsOfChange={changeAsOf}
            navOpened={navOpened}
            onToggleNav={navHandlers.toggle}
          />
        </AppShell.Header>
        {ready && (
          <AppShell.Navbar p="md" hiddenFrom="sm" aria-label="Views">
            {navOpened && (
              <AppNavbar
                view={view}
                onViewChange={setView}
                curveId={curve.id}
                catalogue={curves}
                onCurveChange={changeCurve}
                onNavigate={navHandlers.close}
              />
            )}
          </AppShell.Navbar>
        )}
        <AppShell.Main>
          <Container size={1200} px={{ base: 'md', sm: 'lg' }} py="lg">
            {(state === 'checking' || (state === 'online' && catalogue.kind === 'loading')) && (
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
            {state === 'online' && catalogue.kind === 'error' && (
              <Stack gap="lg">
                <PageHeader title="Curves unavailable" />
                <Alert color="red" role="alert" title="Curve list not loaded" icon={<IconAlertTriangle size={18} />}>
                  <Stack gap="xs" align="flex-start">
                    <Text size="sm">The list of curves could not be loaded. Try again in a moment.</Text>
                    <Button variant="light" size="xs" onClick={retryCatalogue}>
                      Try again
                    </Button>
                  </Stack>
                </Alert>
              </Stack>
            )}
            {state === 'online' && catalogue.kind === 'ok' && curves.length === 0 && (
              <Box role="status">
                <EmptyState
                  title="No curves yet"
                  description="No curves are loaded yet. Check back after the next daily load."
                >
                  <EmptyState.Actions>
                    <Button variant="light" size="xs" onClick={retryCatalogue}>
                      Try again
                    </Button>
                  </EmptyState.Actions>
                </EmptyState>
              </Box>
            )}
            {ready && (
              <Stack gap="lg">
                {simulated && curve && (
                  <Alert color="orange" role="note" py="xs" icon={<IconInfoCircle size={18} />}>
                    {`Simulated scenario data, not published by ${sourceOf(curve).publisher}.`}
                  </Alert>
                )}
                <Tabs.Panel value="curve">
                  <CurveView key={curve.id} curve={curve} catalogue={curves} overlay={overlay} asOf={asOf} />
                </Tabs.Panel>
                <Tabs.Panel value="series">
                  <SeriesView key={curve.id} curveId={curve.id} asOf={asOf} />
                </Tabs.Panel>
                <Tabs.Panel value="changes">
                  <ChangesView key={curve.id} curveId={curve.id} asOf={asOf} />
                </Tabs.Panel>
                <Tabs.Panel value="quality">
                  <QualityView key={curve.id} curve={curve} asOf={asOf} />
                </Tabs.Panel>
              </Stack>
            )}
          </Container>
        </AppShell.Main>
        <AppFooter curve={ready ? curve : undefined} />
      </AppShell>
    </Tabs>
  )
}
