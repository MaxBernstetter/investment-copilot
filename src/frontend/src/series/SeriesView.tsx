import { useEffect, useState } from 'react'
import { Alert, Group, NativeSelect, Paper, Skeleton, Stack, TextInput, Text, VisuallyHidden } from '@mantine/core'
import { readAsOf, writeAsOf } from '../asOf'
import PageHeader from '../layout/PageHeader'
import AsOfControl from '../curve/AsOfControl'
import { curveById } from '../curve/curves'
import { fetchSeries, type SeriesResult } from './fetchSeries'
import SeriesChart from './SeriesChart'
import { defaultRange, MATURITIES } from './seriesData'

const DEFAULT_MATURITY = '10Y'

type SeriesViewProps = {
  curveId: string
}

export default function SeriesView({ curveId }: SeriesViewProps) {
  const [maturity, setMaturity] = useState(DEFAULT_MATURITY)
  const [range, setRange] = useState(() => defaultRange(new Date()))
  const [asOf, setAsOf] = useState<string | undefined>(() => readAsOf(window.location.search))
  const [result, setResult] = useState<SeriesResult | undefined>(undefined)

  useEffect(() => {
    let active = true
    fetchSeries({ curveId, maturity, from: range.from, to: range.to, asOf }).then((next) => {
      if (active) setResult(next)
    })
    return () => {
      active = false
    }
  }, [curveId, maturity, range, asOf])

  const changeAsOf = (next: string | undefined) => {
    setAsOf(next)
    writeAsOf(next)
  }

  const asOfText = asOf ? new Date(asOf).toUTCString() : ''

  return (
    <Stack component="section" gap="md">
      <PageHeader title={`${curveById(curveId).label} time series`} />
      <Group gap="sm" align="flex-end">
        <NativeSelect
          label="Maturity"
          data={MATURITIES}
          value={maturity}
          onChange={(event) => setMaturity(event.currentTarget.value)}
        />
        <TextInput
          type="date"
          label="From"
          value={range.from}
          onChange={(event) => {
            if (event.currentTarget.value) setRange({ ...range, from: event.currentTarget.value })
          }}
        />
        <TextInput
          type="date"
          label="To"
          value={range.to}
          onChange={(event) => {
            if (event.currentTarget.value) setRange({ ...range, to: event.currentTarget.value })
          }}
        />
        <AsOfControl asOf={asOf} onChange={changeAsOf} />
      </Group>
      {asOf && (
        <Alert variant="light" color="blue" role="status">
          Showing the series as known on {asOfText}
        </Alert>
      )}
      {result === undefined && (
        <>
          <Skeleton h={320} />
          <VisuallyHidden>Loading…</VisuallyHidden>
        </>
      )}
      {result?.kind === 'ok' && result.series.data.points.length > 0 && (
        <Paper withBorder p="md">
          <SeriesChart points={result.series.data.points} />
        </Paper>
      )}
      {result?.kind === 'ok' && result.series.data.points.length === 0 && (
        <Alert variant="light" color="blue" role="status">
          No values in this range.
        </Alert>
      )}
      {result?.kind === 'offline' && (
        <Alert color="red" role="alert">
          Backend offline: the YieldLens API is not reachable. Try again later.
        </Alert>
      )}
      {result?.kind === 'not-found' && !asOf && (
        <Alert variant="light" color="blue" role="status">
          No data known for this maturity.
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
