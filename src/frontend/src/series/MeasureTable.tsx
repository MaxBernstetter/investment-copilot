import { Badge, Text, VisuallyHidden } from '@mantine/core'
import DataTable, { type TableColumn } from '../components/DataTable'
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
  const columns: TableColumn<MeasurePoint>[] = [
    { id: 'valid-date', header: 'Valid date', cell: (point) => point.valid_date, filterText: (point) => point.valid_date },
    {
      id: 'value',
      header: 'Value (bp)',
      align: 'right',
      cell: (point) => {
        const value = point[measureKey]
        return value === null || value === undefined ? EMPTY : formatBpPlain(value)
      },
      filterText: (point) => {
        const value = point[measureKey]
        return value === null || value === undefined ? '' : formatBpPlain(value)
      },
    },
    {
      id: 'quality',
      header: 'Quality',
      cell: (point) => <MeasureQualityCell point={point} measureKey={measureKey} />,
      filterText: (point) => measureHint(point, measureKey) ?? STATUS_LABEL[point.quality.status],
    },
  ]
  return (
    <>
      <DataTable columns={columns} rows={points} rowKey={(point) => point.valid_date} />
      {hasUnchecked && <UncheckedNote />}
    </>
  )
}
