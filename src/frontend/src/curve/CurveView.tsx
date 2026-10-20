import { useEffect, useMemo, useState } from 'react'
import { Alert, Button, Group, Paper, Pill, Skeleton, Stack, TextInput, Text, VisuallyHidden } from '@mantine/core'
import { readAsOf, writeAsOf } from '../asOf'
import PageHeader from '../layout/PageHeader'
import AsOfControl from './AsOfControl'
import CurveChart from './CurveChart'
import { missingMaturities, type LabelledCurve } from './curveData'
import { curveById } from './curves'
import { fetchCurve, type CurveResult } from './fetchCurve'
import VersionHistory from '../versions/VersionHistory'

const MAX_OVERLAYS = 5

type CurveViewProps = {
  curveId: string
}

export default function CurveView({ curveId }: CurveViewProps) {
  const [validDate, setValidDate] = useState<string | undefined>(undefined)
  const [asOf, setAsOf] = useState<string | undefined>(() => readAsOf(window.location.search))
  const [result, setResult] = useState<CurveResult | undefined>(undefined)
  const [overlayDates, setOverlayDates] = useState<string[]>([])
  const [overlayCurves, setOverlayCurves] = useState<LabelledCurve[]>([])
  const [historyMaturity, setHistoryMaturity] = useState<string | undefined>(undefined)

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

  const changeAsOf = (next: string | undefined) => {
    setAsOf(next)
    writeAsOf(next)
  }

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

  const missing = result?.kind === 'ok' ? missingMaturities(result.curve.data.points) : []
  const withValue =
    result?.kind === 'ok'
      ? result.curve.data.points.filter((point) => point.value !== null).map((point) => point.maturity)
      : []
  const asOfText = asOf ? new Date(asOf).toUTCString() : ''

  return (
    <Stack component="section" gap="md">
      <PageHeader title={curveById(curveId).label} />
      <Group gap="sm" align="flex-end">
        <TextInput
          type="date"
          label="Valid date"
          value={validDate ?? returnedDate}
          onChange={(event) => setValidDate(event.currentTarget.value || undefined)}
        />
        <AsOfControl asOf={asOf} onChange={changeAsOf} />
      </Group>
      {asOf && (
        <Alert variant="light" color="blue" role="status">
          Showing the curve as known on {asOfText}
        </Alert>
      )}
      {result === undefined && (
        <>
          <Skeleton h={320} />
          <VisuallyHidden>Loading…</VisuallyHidden>
        </>
      )}
      {result?.kind === 'ok' && (
        <>
          <Group gap="sm">
            <Button
              variant="light"
              disabled={!canAddOverlay}
              onClick={() => setOverlayDates((dates) => [...dates, shownDate])}
            >
              Add to overlay
            </Button>
          </Group>
          {overlayDates.length > 0 && (
            <Group component="ul" aria-label="Overlaid valid dates" gap="xs" m={0} p={0} style={{ listStyle: 'none' }}>
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
          <Paper withBorder p="md">
            <CurveChart curves={curves} />
          </Paper>
          {missing.length > 0 && <Text>No value for: {missing.join(', ')}</Text>}
          <Group gap="xs">
            {withValue.map((maturity) => (
              <Button
                key={maturity}
                size="xs"
                variant="subtle"
                onClick={() => setHistoryMaturity(maturity)}
              >
                History {maturity}
              </Button>
            ))}
          </Group>
          {historyMaturity !== undefined && (
            <VersionHistory
              curveId={curveId}
              maturity={historyMaturity}
              validDate={shownDate}
              asOf={asOf}
              onClose={() => setHistoryMaturity(undefined)}
            />
          )}
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
      {result?.kind === 'not-found' && asOf && <Text>No data known as of {asOfText}</Text>}
      {(result?.kind === 'invalid' || result?.kind === 'error') && (
        <Alert color="red" role="alert">
          {result.detail}
        </Alert>
      )}
    </Stack>
  )
}
