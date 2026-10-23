import { Anchor, Box, Container, Divider, Group, Text } from '@mantine/core'
import { ACCESS_URL, APP_VERSION, COMMIT, METHODOLOGY_URL, REPOSITORY_URL } from '../config'
import type { CurveInfo } from '../curve/fetchCurves'
import { sourceOf } from '../curve/sources'

type AppFooterProps = {
  /** The shown curve; without one (loading or unavailable) the attribution line is empty. */
  curve?: CurveInfo
}

function Attribution({ curve }: { curve: CurveInfo }) {
  if (curve.simulated) {
    return `${curve.attribution}. Scenario data, not published by ${sourceOf(curve).publisher}.`
  }
  const { termsUrl } = sourceOf(curve)
  if (termsUrl === undefined) return `${curve.attribution}, ${curve.label}.`
  return (
    <>
      {`${curve.attribution}, ${curve.label}. Reuse with attribution, see the `}
      <Anchor size="xs" href={termsUrl} underline="always">
        ECB copyright notice
      </Anchor>
      .
    </>
  )
}

/** The page footer, in the page flow at the end of the body (not fixed, so it costs no mobile height). */
export default function AppFooter({ curve }: AppFooterProps) {
  return (
    <Box component="footer" style={{ flexShrink: 0 }}>
      <Divider />
      <Container fluid px={{ base: 'md', sm: 'lg' }} py="sm">
        <Group justify="space-between" align="flex-start" gap="md">
          <Text size="xs" c="dimmed" maw={640}>
            {curve && <Attribution curve={curve} />}
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
