import { useEffect, useMemo, useState } from 'react'
import {
  ActionIcon,
  Alert,
  Button,
  Card,
  Group,
  Pill,
  SimpleGrid,
  Skeleton,
  Stack,
  Table,
  TextInput,
  Text,
  Title,
  Tooltip,
  VisuallyHidden,
} from '@mantine/core'
import { IconInfoCircle } from '@tabler/icons-react'
import StatCard from '../components/StatCard'
import { formatBp, formatUtc, formatYield } from '../format'
import PageHeader from '../layout/PageHeader'
import UncheckedNote from '../quality/UncheckedNote'
import ValueQualityCell from '../quality/ValueQualityCell'
import VersionHistory from '../versions/VersionHistory'
import CurveChart from './CurveChart'
import { flaggedMaturities, missingMaturities, spread2s10s, yield10y, type LabelledCurve } from './curveData'
import { curveById } from './curves'
import { fetchCurve, type CurveResult } from './fetchCurve'

const MAX_OVERLAYS = 5
const VALID_DATE_HELP = 'The business day the yield applies to, as published by the ECB.'
const EMPTY = '–'

type CurveViewProps = {
  curveId: string
  /** The knowledge time shared by all views, set in the header. */
  asOf?: string
}

export default function CurveView({ curveId, asOf }: CurveViewProps) {
  const [validDate, setValidDate] = useState<string | undefined>(undefined)
  const [result, setResult] = useState<CurveResult | undefined>(undefined)
  const [overlayDates, setOverlayDates] = useState<string[]>([])
  const [overlayCurves, setOverlayCurves] = useState<LabelledCurve[]>([])
  const [historyMaturity, setHistoryMaturity] = useState<string | undefined>(undefined)

  const curve = curveById(curveId)
  const subtitle = curve.isSimulated
    ? 'Simulated scenario based on ECB AAA spot'
    : 'ECB euro area AAA government bonds, spot rates by maturity'

  useEffect(() => {
    let active = true
    fetchCurve({ curveId, validDate, asOf }).then((next) => {
      if (active) setResult(next)
    })
    return () => {
      active = false
    }
  }, [curveId, validDate, asOf])

  useEffect(() => {
    let active = true
    Promise.all(overlayDates.map((date) => fetchCurve({ curveId, validDate: date, asOf }))).then(
      (results) => {
        if (!active) return
        setOverlayCurves(
          results.flatMap((next, i) =>
            next.kind === 'ok' ? [{ label: overlayDates[i], points: next.curve.data.points }] : [],
          ),
        )
      },
    )
    return () => {
      active = false
    }
  }, [curveId, overlayDates, asOf])

  const returnedDate = result?.kind === 'ok' ? result.curve.data.valid_date : ''
  const shownDate = validDate ?? returnedDate
  const canAddOverlay =
    shownDate !== '' && !overlayDates.includes(shownDate) && overlayDates.length < MAX_OVERLAYS

  const curves = useMemo<LabelledCurve[]>(() => {
    if (result?.kind !== 'ok') return []
    const current = { label: result.curve.data.valid_date, points: result.curve.data.points }
    const overlays = overlayCurves.filter(
      (curve) => overlayDates.includes(curve.label) && curve.label !== current.label,
    )
    return [current, ...overlays]
  }, [result, overlayCurves, overlayDates])

  const points = result?.kind === 'ok' ? result.curve.data.points : []
  const missing = result?.kind === 'ok' ? missingMaturities(points) : []
  const flagged = flaggedMaturities(points)
  const hasUnchecked = points.some((point) => point.quality?.status === 'unchecked')

  const y10 = yield10y(points)
  const spread = spread2s10s(points)

  const headerActions = (
    <>
      <Group gap={4} align="flex-end">
        <TextInput
          type="date"
          label="Valid date"
          value={validDate ?? returnedDate}
          onChange={(event) => setValidDate(event.currentTarget.value || undefined)}
        />
        <Tooltip label={VALID_DATE_HELP}>
          <ActionIcon variant="subtle" size="sm" aria-label="About valid date">
            <IconInfoCircle size={16} />
          </ActionIcon>
        </Tooltip>
      </Group>
      <Button
        variant="default"
        disabled={result?.kind !== 'ok' || !canAddOverlay}
        onClick={() => setOverlayDates((dates) => [...dates, shownDate])}
      >
        Add to overlay
      </Button>
    </>
  )

  return (
    <Stack component="section" gap="lg">
      <PageHeader title="Yield curve" subtitle={subtitle} actions={headerActions} />
      {result === undefined && (
        <>
          <Skeleton h={320} />
          <VisuallyHidden>Loading…</VisuallyHidden>
        </>
      )}
      {result?.kind === 'ok' && (
        <>
          <SimpleGrid cols={{ base: 2, sm: 4 }}>
            <StatCard label="10Y yield" value={y10 === undefined ? EMPTY : formatYield(y10)} />
            <StatCard label="2Y–10Y spread" value={spread === undefined ? EMPTY : formatBp(spread)} />
            <StatCard label="Curve date" value={shownDate} />
            <StatCard label="Knowledge" value={asOf ? formatUtc(asOf) : 'Live'} />
          </SimpleGrid>
          <Card>
            <Group justify="space-between" align="center" wrap="wrap" gap="sm" mb="md">
              <Title order={2}>Spot curve (%)</Title>
              {overlayDates.length > 0 && (
                <Group component="ul" aria-label="Overlaid valid dates" gap="xs" m={0} p={0}>
                  {overlayDates.map((date) => (
                    <Pill
                      key={date}
                      component="li"
                      withRemoveButton
                      removeButtonProps={{ 'aria-label': `Remove ${date}`, 'aria-hidden': false, tabIndex: 0 }}
                      onRemove={() => setOverlayDates((dates) => dates.filter((d) => d !== date))}
                    >
                      {date}
                    </Pill>
                  ))}
                </Group>
              )}
            </Group>
            <CurveChart curves={curves} />
            {(missing.length > 0 || flagged.length > 0) && (
              <Stack gap={4} mt="sm">
                {missing.length > 0 && <Text size="sm" c="dimmed">No value for: {missing.join(', ')}</Text>}
                {flagged.length > 0 && <Text size="sm" c="dimmed">Flagged: {flagged.join(', ')}</Text>}
              </Stack>
            )}
          </Card>
          <Card>
            <Title order={2} mb="md">Values</Title>
            <Table.ScrollContainer minWidth={560}>
              <Table>
                <Table.Thead>
                  <Table.Tr>
                    <Table.Th scope="col">Maturity</Table.Th>
                    <Table.Th scope="col" ta="right">Yield (%)</Table.Th>
                    <Table.Th scope="col">Quality</Table.Th>
                    <Table.Th scope="col" />
                  </Table.Tr>
                </Table.Thead>
                <Table.Tbody>
                  {points.map((point) => (
                    <Table.Tr key={point.maturity}>
                      <Table.Td>{point.maturity}</Table.Td>
                      <Table.Td ta="right">
                        {point.value === null ? EMPTY : formatYield(point.value)}
                      </Table.Td>
                      <Table.Td>
                        <ValueQualityCell quality={point.quality} maturity={point.maturity} />
                      </Table.Td>
                      <Table.Td>
                        {point.value !== null && (
                          <Button
                            size="compact-xs"
                            variant="subtle"
                            aria-label={`History ${point.maturity}`}
                            onClick={() => setHistoryMaturity(point.maturity)}
                          >
                            History
                          </Button>
                        )}
                      </Table.Td>
                    </Table.Tr>
                  ))}
                </Table.Tbody>
              </Table>
            </Table.ScrollContainer>
            {hasUnchecked && <UncheckedNote />}
          </Card>
          <VersionHistory
            curveId={curveId}
            maturity={historyMaturity ?? ''}
            validDate={shownDate}
            asOf={asOf}
            opened={historyMaturity !== undefined}
            onClose={() => setHistoryMaturity(undefined)}
          />
        </>
      )}
      {result?.kind === 'offline' && (
        <Alert color="red" role="alert">
          Backend offline: the YieldLens API is not reachable. Try again later.
        </Alert>
      )}
      {result?.kind === 'not-found' && !asOf && (
        <Alert variant="light" color="blue" role="status">
          No data known for this date.
        </Alert>
      )}
      {result?.kind === 'not-found' && asOf && <Text>No data known as of {formatUtc(asOf)}</Text>}
      {(result?.kind === 'invalid' || result?.kind === 'error') && (
        <Alert color="red" role="alert">
          {result.detail}
        </Alert>
      )}
    </Stack>
  )
}
