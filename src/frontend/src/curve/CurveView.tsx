import { useEffect, useMemo, useState } from 'react'
import {
  ActionIcon,
  Alert,
  Badge,
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
import { IconArrowsDownUp, IconInfoCircle } from '@tabler/icons-react'
import StatCard from '../components/StatCard'
import { COMPOUNDING, EMPTY, RATE_TYPE, formatUtc, formatYield, unitSymbol } from '../format'
import PageHeader from '../layout/PageHeader'
import UncheckedNote from '../quality/UncheckedNote'
import ValueQualityCell from '../quality/ValueQualityCell'
import VersionHistory from '../versions/VersionHistory'
import CurveChart from './CurveChart'
import { flaggedMaturities, missingMaturities, tenYearHint, yield10y, type LabelledCurve } from './curveData'
import type { CurveInfo } from './fetchCurves'
import { fetchCurve, type CurveResult } from './fetchCurve'
import { fetchMeasures, type MeasuresResult } from './fetchMeasures'
import { measureHint, measureValue, type MeasurePoint } from './measuresData'
import { validDateHelp } from './sources'

const MAX_OVERLAYS = 5
const HELP_10Y = 'Spot rate for a 10-year maturity on this valid date, in percent.'
const HELP_2Y_10Y =
  '10Y yield minus 2Y yield, in basis points. Also called the slope. Below zero the curve is inverted.'
const HELP_3M_10Y =
  '10Y yield minus 3M yield, in basis points. Compares the long end with the money-market end of the curve.'
const HELP_CURVATURE =
  '2 × 5Y \u2212 2Y \u2212 10Y, in basis points. Positive means a humped belly: 5Y is above the average of 2Y and 10Y. Negative means a sagging belly.'

type CurveViewProps = {
  curve: CurveInfo
  /** The knowledge time shared by all views, set in the header. */
  asOf?: string
}

export default function CurveView({ curve, asOf }: CurveViewProps) {
  const [validDate, setValidDate] = useState<string | undefined>(undefined)
  const [result, setResult] = useState<CurveResult | undefined>(undefined)
  const [overlayDates, setOverlayDates] = useState<string[]>([])
  const [overlayCurves, setOverlayCurves] = useState<LabelledCurve[]>([])
  const [historyMaturity, setHistoryMaturity] = useState<string | undefined>(undefined)
  const [measures, setMeasures] = useState<{ key: string; result: MeasuresResult } | undefined>(undefined)

  const measuresKey =
    result?.kind === 'ok' ? `${curve.id}|${result.curve.data.valid_date}|${result.curve.meta.as_of}` : undefined

  // The measures are for the curve answer's valid date at its as_of, so one answer sets both.
  useEffect(() => {
    if (result?.kind !== 'ok') return
    const date = result.curve.data.valid_date
    const asOfUsed = result.curve.meta.as_of
    const key = `${curve.id}|${date}|${asOfUsed}`
    let active = true
    fetchMeasures({ curveId: curve.id, from: date, to: date, asOf: asOfUsed }).then((next) => {
      if (active) setMeasures({ key, result: next })
    })
    return () => {
      active = false
    }
  }, [curve.id, result])

  const subtitle = `${curve.label} · ${RATE_TYPE[curve.rateType].toLowerCase()} rates, ${COMPOUNDING[curve.compounding]} compounding`

  useEffect(() => {
    let active = true
    fetchCurve({ curveId: curve.id, validDate, asOf }).then((next) => {
      if (active) setResult(next)
    })
    return () => {
      active = false
    }
  }, [curve.id, validDate, asOf])

  useEffect(() => {
    let active = true
    Promise.all(overlayDates.map((date) => fetchCurve({ curveId: curve.id, validDate: date, asOf }))).then(
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
  }, [curve.id, overlayDates, asOf])

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
  const measuresLoading = measuresKey !== undefined && measures?.key !== measuresKey
  const measurePoint: MeasurePoint | undefined =
    !measuresLoading && measures?.result.kind === 'ok'
      ? measures.result.measures.data.points.find((point) => point.valid_date === returnedDate)
      : undefined

  const headerActions = (
    <>
      <Group gap={4} align="flex-end">
        <TextInput
          type="date"
          label="Valid date"
          value={validDate ?? returnedDate}
          onChange={(event) => setValidDate(event.currentTarget.value || undefined)}
        />
        <Tooltip label={validDateHelp(curve)}>
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
          <SimpleGrid cols={{ base: 2, sm: 4 }} aria-busy={measuresLoading || undefined}>
            <StatCard
              label="10Y yield"
              help={HELP_10Y}
              value={y10 === undefined ? EMPTY : formatYield(y10)}
              hint={tenYearHint(points)}
            />
            <StatCard
              label="2Y–10Y spread"
              help={HELP_2Y_10Y}
              loading={measuresLoading}
              value={measureValue(measurePoint, 'spread_2y_10y')}
              hint={measureHint(measurePoint, 'spread_2y_10y')}
              badge={
                measurePoint?.inverted === true ? (
                  <Badge color="gray" variant="light" size="sm" leftSection={<IconArrowsDownUp size={12} aria-hidden />}>
                    Inverted
                  </Badge>
                ) : undefined
              }
            />
            <StatCard
              label="3M–10Y spread"
              help={HELP_3M_10Y}
              loading={measuresLoading}
              value={measureValue(measurePoint, 'spread_3m_10y')}
              hint={measureHint(measurePoint, 'spread_3m_10y')}
            />
            <StatCard
              label="2Y–5Y–10Y curvature"
              help={HELP_CURVATURE}
              loading={measuresLoading}
              value={measureValue(measurePoint, 'curvature_2y_5y_10y')}
              hint={measureHint(measurePoint, 'curvature_2y_5y_10y')}
            />
          </SimpleGrid>
          <Card>
            <Group justify="space-between" align="center" wrap="wrap" gap="sm" mb="md">
              <Title order={2}>{`${RATE_TYPE[curve.rateType]} curve (${unitSymbol(curve.unit)})`}</Title>
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
            curveId={curve.id}
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
