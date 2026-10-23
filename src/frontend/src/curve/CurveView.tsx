import { useEffect, useId, useMemo, useRef, useState } from 'react'
import {
  ActionIcon,
  Alert,
  Badge,
  Button,
  Box,
  Card,
  EmptyState,
  Grid,
  Group,
  SimpleGrid,
  Skeleton,
  Stack,
  TextInput,
  Text,
  Title,
  Tooltip,
  VisuallyHidden,
} from '@mantine/core'
import { IconArrowsDownUp, IconInfoCircle } from '@tabler/icons-react'
import DataTable from '../components/DataTable'
import StatCard from '../components/StatCard'
import { COMPOUNDING, EMPTY, RATE_TYPE, formatUtc, formatYield, unitSymbol } from '../format'
import PageHeader from '../layout/PageHeader'
import { STATUS_LABEL } from '../quality/qualityData'
import UncheckedNote from '../quality/UncheckedNote'
import ValueQualityCell from '../quality/ValueQualityCell'
import VersionHistory from '../versions/VersionHistory'
import CurveChart from './CurveChart'
import OverlayEntries from './OverlayEntries'
import OverlayNotes from './OverlayNotes'
import OverlayTable from './OverlayTable'
import {
  distinctCurves,
  entryKey,
  flaggedMaturities,
  missingMaturities,
  tenYearHint,
  yield10y,
  type LabelledCurve,
  type OverlayEntry,
} from './curveData'
import type { CurveInfo } from './fetchCurves'
import { fetchCurve, type CurveResult } from './fetchCurve'
import { fetchMeasures, type MeasuresResult } from './fetchMeasures'
import { MEASURE_HELP, MEASURE_LABEL, measureHint, measureValue, type MeasurePoint } from './measuresData'
import { gapNotes, validDateHelp } from './sources'
import { MAX_OVERLAYS, type CanAdd, type OverlayState } from './useOverlay'

const HELP_10Y = 'Spot rate for a 10-year maturity on this valid date, in percent.'
const HINT: Record<Exclude<CanAdd, 'ok'>, string> = {
  duplicate: 'This curve and date are already in the chart.',
  full: `The overlay holds ${MAX_OVERLAYS} curves. Remove one to add another.`,
}

type CurveViewProps = {
  curve: CurveInfo
  /** The whole catalogue, for the labels of the overlay entries. */
  catalogue: readonly CurveInfo[]
  /** The pinned overlay, owned by App so it survives a curve switch. */
  overlay: OverlayState
  /** The knowledge time shared by all views, set in the header. */
  asOf?: string
}

export default function CurveView({ curve, catalogue, overlay, asOf }: CurveViewProps) {
  const [validDate, setValidDate] = useState<string | undefined>(undefined)
  const [result, setResult] = useState<CurveResult | undefined>(undefined)
  const [overlayData, setOverlayData] = useState<{ asOf: string | undefined; results: Record<string, CurveResult> }>({
    asOf: undefined,
    results: {},
  })
  const [overlayRetry, setOverlayRetry] = useState(0)
  const [announcement, setAnnouncement] = useState('')
  const [historyMaturity, setHistoryMaturity] = useState<string | undefined>(undefined)
  const [measures, setMeasures] = useState<{ key: string; result: MeasuresResult } | undefined>(undefined)
  const hintId = useId()
  const addRef = useRef<HTMLButtonElement>(null)
  const pillsRef = useRef<HTMLUListElement>(null)
  /** Where focus goes after a pill is removed or added: a pill's index, or the add button. A new object per request. */
  const [focusRequest, setFocusRequest] = useState<{ target: number | 'add' } | undefined>(undefined)

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

  const { entries } = overlay

  useEffect(() => {
    let active = true
    for (const entry of entries) {
      fetchCurve({ curveId: entry.curveId, validDate: entry.validDate, asOf }).then((next) => {
        if (!active) return
        setOverlayData((current) => ({
          asOf,
          results: { ...(current.asOf === asOf ? current.results : {}), [entryKey(entry)]: next },
        }))
      })
    }
    return () => {
      active = false
    }
  }, [entries, asOf, overlayRetry])

  // Keyed on the request, so it runs after the commit that already has the updated pills.
  useEffect(() => {
    if (focusRequest === undefined) return
    const { target } = focusRequest
    if (target === 'add') addRef.current?.focus()
    else pillsRef.current?.querySelectorAll<HTMLButtonElement>('button')[target]?.focus()
  }, [focusRequest])

  const labels = useMemo(() => new Map(catalogue.map((info) => [info.id, info.label])), [catalogue])
  const labelOf = (curveId: string) => labels.get(curveId) ?? curveId
  // Results from an earlier knowledge time are not shown; the effect above replaces them.
  const overlayResults = useMemo(
    () => (overlayData.asOf === asOf ? overlayData.results : {}),
    [overlayData, asOf],
  )
  const overlayLoading = entries.some((entry) => overlayResults[entryKey(entry)] === undefined)

  const returnedDate = result?.kind === 'ok' ? result.curve.data.valid_date : ''
  const shownDate = validDate ?? returnedDate
  const shownKey = entryKey({ curveId: curve.id, validDate: returnedDate })

  const curves = useMemo<LabelledCurve[]>(() => {
    if (result?.kind !== 'ok') return []
    const shownEntry = entries.find((entry) => entryKey(entry) === shownKey)
    const overlays = entries.flatMap((entry): LabelledCurve[] => {
      const key = entryKey(entry)
      const loaded = overlayResults[key]
      if (key === shownKey || loaded?.kind !== 'ok') return []
      return [
        {
          key,
          label: `${labels.get(entry.curveId) ?? entry.curveId} · ${entry.validDate}`,
          points: loaded.curve.data.points,
          slot: entry.slot,
        },
      ]
    })
    const shown: LabelledCurve = {
      key: shownKey,
      label: `${curve.label} · ${returnedDate}`,
      points: result.curve.data.points,
      // The shown curve keeps the colour of its entry when it is pinned too.
      slot: shownEntry?.slot ?? 0,
    }
    return [shown, ...overlays]
  }, [curve.label, entries, labels, overlayResults, result, returnedDate, shownKey])

  const addEntry: OverlayEntry = { curveId: curve.id, validDate: shownDate }
  const addState: CanAdd = shownDate === '' ? 'ok' : overlay.canAdd(addEntry)
  const hint = result?.kind === 'ok' && addState !== 'ok' ? HINT[addState] : undefined

  const seriesCount = (keys: string[]) => new Set(keys).size
  const inChart = (count: number) => `${count} ${count === 1 ? 'curve' : 'curves'} in the chart.`

  const onAdd = () => {
    setFocusRequest({ target: entries.length })
    overlay.add(addEntry)
    const count = seriesCount([shownKey, ...entries.map(entryKey), entryKey(addEntry)])
    setAnnouncement(`Added ${labelOf(curve.id)} · ${shownDate} to the overlay. ${inChart(count)}`)
  }

  const onRemove = (index: number) => {
    const removed = entries[index]
    const remaining = entries.filter((_, i) => i !== index)
    setFocusRequest({ target: remaining.length === 0 ? 'add' : Math.min(index, remaining.length - 1) })
    overlay.remove(removed)
    const count = seriesCount([shownKey, ...remaining.map(entryKey)])
    setAnnouncement(`Removed ${labelOf(removed.curveId)} · ${removed.validDate} from the overlay. ${inChart(count)}`)
  }

  // The curves drawn: the shown one and each overlay entry that loaded. Failed or empty entries are not listed.
  const drawnCurves = useMemo(
    () =>
      distinctCurves(
        [
          { curveId: curve.id, validDate: returnedDate },
          ...entries.filter((entry) => overlayResults[entryKey(entry)]?.kind === 'ok'),
        ],
        catalogue,
      ),
    [catalogue, curve.id, entries, overlayResults, returnedDate],
  )

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
      <TextInput
        type="date"
        label={
          <Group gap={4} component="span" wrap="nowrap">
            Valid date
            <Tooltip label={validDateHelp(curve)}>
              <ActionIcon component="span" role="button" tabIndex={0} variant="subtle" size="xs" aria-label="About valid date">
                <IconInfoCircle size={14} />
              </ActionIcon>
            </Tooltip>
          </Group>
        }
        value={validDate ?? returnedDate}
        onChange={(event) => setValidDate(event.currentTarget.value || undefined)}
      />
      <Button
        variant="default"
        ref={addRef}
        disabled={result?.kind !== 'ok' || addState !== 'ok'}
        aria-describedby={hint ? hintId : undefined}
        onClick={onAdd}
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
              label={MEASURE_LABEL.spread_2y_10y}
              help={MEASURE_HELP.spread_2y_10y}
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
              label={MEASURE_LABEL.spread_3m_10y}
              help={MEASURE_HELP.spread_3m_10y}
              loading={measuresLoading}
              value={measureValue(measurePoint, 'spread_3m_10y')}
              hint={measureHint(measurePoint, 'spread_3m_10y')}
            />
            <StatCard
              label={MEASURE_LABEL.curvature_2y_5y_10y}
              help={MEASURE_HELP.curvature_2y_5y_10y}
              loading={measuresLoading}
              value={measureValue(measurePoint, 'curvature_2y_5y_10y')}
              hint={measureHint(measurePoint, 'curvature_2y_5y_10y')}
            />
          </SimpleGrid>
          <Grid>
            <Grid.Col span={{ base: 12, lg: 7 }}>
            <Card aria-busy={overlayLoading || undefined}>
              <Title order={2} mb="md">{`${RATE_TYPE[curve.rateType]} curve (${unitSymbol(curve.unit)})`}</Title>
              {entries.length > 0 && (
                <OverlayEntries entries={entries} labelOf={labelOf} listRef={pillsRef} onRemove={onRemove} />
              )}
              {hint && (
                <Text id={hintId} size="sm" fw={500} mb="md">
                  {hint}
                </Text>
              )}
              <VisuallyHidden aria-live="polite" aria-atomic>
                {announcement}
              </VisuallyHidden>
              <CurveChart curves={curves} />
              {entries.length > 0 && <OverlayNotes curves={drawnCurves} drawn={curves} />}
              {(missing.length > 0 || flagged.length > 0) && (
                <Stack gap={4} mt="sm">
                  {gapNotes(curve, missing).map((note) => (
                    <Text key={note} size="sm">
                      {note}
                    </Text>
                  ))}
                  {flagged.length > 0 && <Text size="sm">Flagged: {flagged.join(', ')}</Text>}
                </Stack>
              )}
              {entries.length > 0 && <OverlayTable curves={curves} />}
              {entries.map((entry) => {
                const loaded = overlayResults[entryKey(entry)]
                const name = `${labelOf(entry.curveId)} · ${entry.validDate}`
                if (loaded === undefined || loaded.kind === 'ok') return null
                if (loaded.kind === 'not-found') {
                  return (
                    <Text key={entryKey(entry)} size="sm" c="dimmed" mt="sm">
                      {`No data for ${labelOf(entry.curveId)} on ${entry.validDate}.`}
                    </Text>
                  )
                }
                return (
                  <Alert key={entryKey(entry)} color="red" mt="sm" title={`Could not load ${name}`}>
                    <Stack gap="xs" align="flex-start">
                      <Text size="sm">Check your connection and try again.</Text>
                      <Button variant="light" size="xs" onClick={() => setOverlayRetry((count) => count + 1)}>
                        Try again
                      </Button>
                    </Stack>
                  </Alert>
                )
              })}
            </Card>
            </Grid.Col>
            <Grid.Col span={{ base: 12, lg: 5 }}>
            {/* From lg up the card is taken out of the flow and fills the row, so the chart sets the shared height. */}
            <Box pos="relative" h="100%">
            <Card
              pos={{ base: 'static', lg: 'absolute' }}
              top={0}
              bottom={0}
              left={0}
              right={0}
              style={{ display: 'flex', flexDirection: 'column' }}
            >
              <Title order={2} mb="md">Values</Title>
              <Box flex={{ base: 'none', lg: 1 }} h={{ base: 420, lg: 'auto' }} mih={0}>
              <DataTable
                fill
                columns={[
                  {
                    id: 'maturity',
                    header: 'Maturity',
                    cell: (point) => point.maturity,
                    kind: 'category',
                    filterValue: (point) => point.maturity,
                  },
                  {
                    id: 'yield',
                    header: 'Yield (%)',
                    align: 'right',
                    cell: (point) => (point.value === null ? EMPTY : formatYield(point.value)),
                    kind: 'number',
                    filterValue: (point) => point.value,
                  },
                  {
                    id: 'quality',
                    header: 'Quality',
                    cell: (point) => <ValueQualityCell quality={point.quality} maturity={point.maturity} />,
                    kind: 'category',
                    filterValue: (point) => (point.quality === null ? null : STATUS_LABEL[point.quality.status]),
                  },
                  {
                    id: 'history',
                    header: 'History',
                    cell: (point) =>
                      point.value !== null && (
                        <Button
                          size="compact-xs"
                          variant="subtle"
                          aria-label={`History ${point.maturity}`}
                          onClick={() => setHistoryMaturity(point.maturity)}
                        >
                          History
                        </Button>
                      ),
                  },
                ]}
                rows={points}
                rowKey={(point) => point.maturity}
              />
              </Box>
              {hasUnchecked && <UncheckedNote />}
            </Card>
            </Box>
            </Grid.Col>
          </Grid>
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
        <Box role="status">
          <EmptyState
            title="No data for this date"
            description={`YieldLens has no values for ${curve.label} on ${shownDate || 'this date'}.`}
          >
            <EmptyState.Actions>
              <Button variant="light" size="xs" onClick={() => setValidDate(undefined)}>
                Show latest date
              </Button>
            </EmptyState.Actions>
          </EmptyState>
        </Box>
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
