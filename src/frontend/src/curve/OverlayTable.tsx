import { Box, VisuallyHidden } from '@mantine/core'
import DataTable, { type TableColumn } from '../components/DataTable'
import { monthsLabel, type LabelledCurve } from './curveData'

type OverlayTableProps = {
  /** The curves drawn in the chart, in legend order. */
  curves: LabelledCurve[]
}

type Row = { key: string; label: string; values: Map<number, number | null | undefined> }

/**
 * The table equivalent of the overlay chart (D5): one row per drawn curve·date entry, one column per tenor.
 * A tenor an entry does not publish is an empty cell with a visually hidden "No value".
 */
export default function OverlayTable({ curves }: OverlayTableProps) {
  const tenors = [...new Set(curves.flatMap(({ points }) => points.map((point) => point.months)))].sort((a, b) => a - b)
  const caption = `Overlaid curves: ${curves.map(({ label }) => label).join(', ')}`
  const rows: Row[] = curves.map(({ key, label, points }) => ({
    key,
    label,
    values: new Map(points.map((point) => [point.months, point.value])),
  }))
  const columns: TableColumn<Row>[] = [
    { id: 'curve', header: 'Curve · date', rowHeader: true, width: 220, cell: (row) => row.label, filterText: (row) => row.label },
    ...tenors.map((tenor): TableColumn<Row> => {
      const valueOf = (row: Row) => row.values.get(tenor)
      return {
        id: `tenor-${tenor}`,
        header: monthsLabel(tenor),
        align: 'right',
        cell: (row) => {
          const value = valueOf(row)
          return value === null || value === undefined ? <VisuallyHidden>No value</VisuallyHidden> : value.toFixed(3)
        },
        filterText: (row) => {
          const value = valueOf(row)
          return value === null || value === undefined ? '' : value.toFixed(3)
        },
      }
    }),
  ]
  return (
    <Box mt="md">
      <DataTable caption={caption} columns={columns} rows={rows} rowKey={(row) => row.key} />
    </Box>
  )
}
