import { useEffect, useState } from 'react'
import { AppShell, Alert, Badge, Container, Group, Loader, SegmentedControl, Tabs, Text, Title } from '@mantine/core'
import { isBackendOnline } from './backend'
import ChangesView from './changes/ChangesView'
import CurveView from './curve/CurveView'
import { curveById, readCurveId, writeCurveId } from './curve/curves'
import SeriesView from './series/SeriesView'

type BackendState = 'checking' | 'online' | 'offline'
export default function App() {
  const [state, setState] = useState<BackendState>('checking')
  const [view, setView] = useState<string | null>('curve')
  const [curveId, setCurveId] = useState(() => readCurveId(window.location.search))
  const simulated = curveById(curveId).isSimulated

  const changeCurve = (next: string) => {
    setCurveId(next)
    writeCurveId(next)
  }

  useEffect(() => {
    let active = true
    isBackendOnline().then((online) => {
      if (active) setState(online ? 'online' : 'offline')
    })
    return () => {
      active = false
    }
  }, [])

  return (
    <Tabs value={view} onChange={setView}>
      <AppShell header={{ height: 56 }} padding="md">
        <AppShell.Header>
          <Group h="100%" px="md" justify="space-between" wrap="nowrap">
            <Title order={3}>YieldLens</Title>
            {state === 'online' && (
              <Group gap="sm" wrap="nowrap">
                <SegmentedControl
                  aria-label="Curve"
                  size="xs"
                  value={curveId}
                  onChange={changeCurve}
                  data={[
                    { label: 'Real', value: 'ecb-aaa-spot' },
                    { label: 'Simulated', value: 'ecb-aaa-spot-sim' },
                  ]}
                />
                {simulated && (
                  <Badge color="orange" variant="filled">
                    Simulated
                  </Badge>
                )}
                <Tabs.List>
                  <Tabs.Tab value="curve">Curve</Tabs.Tab>
                  <Tabs.Tab value="series">Time series</Tabs.Tab>
                  <Tabs.Tab value="changes">Changes</Tabs.Tab>
                </Tabs.List>
              </Group>
            )}
          </Group>
        </AppShell.Header>
        <AppShell.Main>
          <Container size="lg">
            {state === 'checking' && (
              <Group gap="xs">
                <Loader size="sm" />
                <Text>Loading…</Text>
              </Group>
            )}
            {state === 'offline' && (
              <Alert color="red" role="alert">
                Backend offline: the YieldLens API is not reachable. Try again later.
              </Alert>
            )}
            {state === 'online' && (
              <>
                {simulated && (
                  <Alert color="orange" variant="light" role="note" mb="md">
                    Simulated data from a scenario, not real source data.
                  </Alert>
                )}
                <Tabs.Panel value="curve">
                  <CurveView key={curveId} curveId={curveId} />
                </Tabs.Panel>
                <Tabs.Panel value="series">
                  <SeriesView key={curveId} curveId={curveId} />
                </Tabs.Panel>
                <Tabs.Panel value="changes">
                  <ChangesView key={curveId} curveId={curveId} />
                </Tabs.Panel>
              </>
            )}
          </Container>
        </AppShell.Main>
      </AppShell>
    </Tabs>
  )
}
