import { useEffect, useState } from 'react'
import { AppShell, Alert, Container, Group, Loader, Tabs, Text, Title } from '@mantine/core'
import { isBackendOnline } from './backend'
import CurveView from './curve/CurveView'
import SeriesView from './series/SeriesView'

type BackendState = 'checking' | 'online' | 'offline'
export default function App() {
  const [state, setState] = useState<BackendState>('checking')
  const [view, setView] = useState<string | null>('curve')

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
              <Tabs.List>
                <Tabs.Tab value="curve">Curve</Tabs.Tab>
                <Tabs.Tab value="series">Time series</Tabs.Tab>
              </Tabs.List>
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
                <Tabs.Panel value="curve">
                  <CurveView />
                </Tabs.Panel>
                <Tabs.Panel value="series">
                  <SeriesView />
                </Tabs.Panel>
              </>
            )}
          </Container>
        </AppShell.Main>
      </AppShell>
    </Tabs>
  )
}
