import { Badge, Table, Text, VisuallyHidden } from '@mantine/core'
import { measureHint, type MeasureKey, type MeasurePoint } from '../curve/measuresData'
import { EMPTY, formatBpPlain } from '../format'
import UncheckedNote from '../quality/UncheckedNote'
import { STATUS_LABEL } from '../quality/qualityData'
import { qualityBadgeProps } from '../theme'

/** The dimmed hint for a null or flagged day (C5); otherwise the status, hidden when passed. */
function MeasureQualityCell({ point, measureKey }: { point: MeasurePoint; measureKey: MeasureKey }) {
  const hint = measureHint(point, measureKey)
  if (hint !== undefined) return <Text size="sm" c="dimmed">{hint}</Text>
  if (point.quality.status === 'passed') return <VisuallyHidden>{STATUS_LABEL.passed}</VisuallyHidden>
  return <Badge {...qualityBadgeProps(point.quality.status)}>{STATUS_LABEL[point.quality.status]}</Badge>
}

type MeasureTableProps = {
  points: MeasurePoint[]
  measureKey: MeasureKey
}

/** Valid date, value in bp without the unit (the header carries it), and quality for each day. */
export default function MeasureTable({ points, measureKey }: MeasureTableProps) {
  const hasUnchecked = points.some((point) => point.quality.status === 'unchecked')
  return (
    <>
      <Table.ScrollContainer minWidth={560}>
        <Table>
          <Table.Thead>
            <Table.Tr>
              <Table.Th scope="col">Valid date</Table.Th>
              <Table.Th scope="col" ta="right">Value (bp)</Table.Th>
              <Table.Th scope="col">Quality</Table.Th>
            </Table.Tr>
          </Table.Thead>
          <Table.Tbody>
            {points.map((point) => {
              const value = point[measureKey]
              return (
                <Table.Tr key={point.valid_date}>
                  <Table.Td>{point.valid_date}</Table.Td>
                  <Table.Td ta="right">{value === null || value === undefined ? EMPTY : formatBpPlain(value)}</Table.Td>
                  <Table.Td>
                    <MeasureQualityCell point={point} measureKey={measureKey} />
                  </Table.Td>
                </Table.Tr>
              )
            })}
          </Table.Tbody>
        </Table>
      </Table.ScrollContainer>
      {hasUnchecked && <UncheckedNote />}
    </>
  )
}
