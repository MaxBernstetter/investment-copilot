import { Anchor, Box, Container, Divider, Group, Text } from '@mantine/core'
import { ACCESS_URL, APP_VERSION, COMMIT, METHODOLOGY_URL, REPOSITORY_URL } from '../config'

type AppFooterProps = {
  simulated: boolean
}

/** The page footer, in the page flow at the end of the body (not fixed, so it costs no mobile height). */
export default function AppFooter({ simulated }: AppFooterProps) {
  return (
    <Box component="footer">
      <Divider />
      <Container size={1200} px={{ base: 'md', sm: 'lg' }} py="lg">
        <Group justify="space-between" align="flex-start" gap="md">
          <Text size="xs" c="dimmed" maw={640}>
            {simulated ? (
              'Scenario data, not published by the ECB.'
            ) : (
              <>
                Source: <Anchor size="xs" href="https://data.ecb.europa.eu/">ECB statistics</Anchor>, euro area AAA
                government bond spot rates. Reuse with attribution, see the{' '}
                <Anchor size="xs" href="https://www.ecb.europa.eu/services/using-our-site/disclaimer/html/index.en.html">
                  ECB copyright notice
                </Anchor>
                .
              </>
            )}
          </Text>
          <Group gap="md">
            <Anchor size="xs" href={`${ACCESS_URL}/docs`}>
              API docs
            </Anchor>
            <Anchor size="xs" href={METHODOLOGY_URL}>
              Methodology
            </Anchor>
            <Anchor size="xs" href={REPOSITORY_URL}>
              GitHub
            </Anchor>
            <Text size="xs" c="dimmed">
              {`v${APP_VERSION} · ${COMMIT}`}
            </Text>
          </Group>
        </Group>
      </Container>
    </Box>
  )
}
