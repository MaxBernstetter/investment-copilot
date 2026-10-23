import { Alert, List, Stack, Text, Title } from '@mantine/core'
import { IconInfoCircle } from '@tabler/icons-react'
import { COMPOUNDING, RATE_TYPE } from '../format'
import {
  comparabilityIssue,
  monthsLabel,
  tenorGaps,
  type ComparabilityIssue,
  type LabelledCurve,
  type TenorGap,
} from './curveData'
import type { CurveInfo } from './fetchCurves'

const unique = (values: string[]) => [...new Set(values)]

const CONVENTION_END = 'A gap between lines can come from the convention, not from the market.'

/** The note under an overlay chart whose curves differ in convention, or undefined when they agree. */
function comparabilityText(issue: ComparabilityIssue, curves: CurveInfo[]): string {
  const rateTypes = unique(curves.map((curve) => RATE_TYPE[curve.rateType].toLowerCase())).join(', ')
  const compoundings = unique(curves.map((curve) => COMPOUNDING[curve.compounding])).join(', ')
  const rate = `rate types differ (${rateTypes})`
  const compounding = `compounding differs (${compoundings})`
  const differences = {
    'rate-type': rate,
    compounding,
    both: `${rate} and ${compounding}`,
  }[issue]
  return `These curves are not directly comparable: ${differences}. ${CONVENTION_END}`
}

/** The source line of each distinct attribution, with the labels of the curves it covers, in order of first appearance. */
function attributionLines(curves: CurveInfo[]): { text: string; labels: string[] }[] {
  const groups = new Map<string, string[]>()
  for (const curve of curves) {
    groups.set(curve.attribution, [...(groups.get(curve.attribution) ?? []), curve.label])
  }
  return [...groups].map(([text, labels]) => ({ text, labels }))
}

/** The missing-value line for one drawn curve; more than 8 tenors are counted, not listed. */
function gapText({ label, months }: TenorGap): string {
  if (months.length > 8) return `No value on ${label} for ${months.length} maturities.`
  return `No value on ${label}: ${months.map(monthsLabel).join(', ')}.`
}

type OverlayNotesProps = {
  /** The distinct curves drawn in the chart, the shown one included. */
  curves: CurveInfo[]
  /** The drawn curves in the chart, to find the tenors each one lacks. */
  drawn?: LabelledCurve[]
}

/**
 * Notes under an overlay chart, in this order: the comparability note when conventions differ,
 * one missing-value line per curve with gaps, then one attribution per source.
 */
export default function OverlayNotes({ curves, drawn = [] }: OverlayNotesProps) {
  const issue = comparabilityIssue(curves)
  return (
    <Stack gap="sm" mt="sm">
      {issue !== undefined && (
        <Alert variant="light" color="blue" role="note" icon={<IconInfoCircle size={16} />}>
          {comparabilityText(issue, curves)}
        </Alert>
      )}
      {tenorGaps(drawn).map((gap) => (
        <Text key={gap.label} size="sm" c="dimmed">
          {gapText(gap)}
        </Text>
      ))}
      <div>
        <Title order={3} size="h5" mb={4}>
          Attribution
        </Title>
        <List size="sm" c="dimmed" spacing={4}>
          {attributionLines(curves).map(({ text, labels }) => (
            <List.Item key={text}>{`${text} (${labels.join(', ')})`}</List.Item>
          ))}
        </List>
      </div>
    </Stack>
  )
}
