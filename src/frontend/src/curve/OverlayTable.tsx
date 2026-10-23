import { Table, VisuallyHidden } from '@mantine/core'
import { monthsLabel, type LabelledCurve } from './curveData'

type OverlayTableProps = {
  /** The curves drawn in the chart, in legend order. */
  curves: LabelledCurve[]
}

/**
 * The table equivalent of the overlay chart (D5): one row per drawn curve·date entry, one column per tenor.
 * A tenor an entry does not publish is an empty cell with a visually hidden "No value".
 */
export default function OverlayTable({ curves }: OverlayTableProps) {
  const tenors = [...new Set(curves.flatMap(({ points }) => points.map((point) => point.months)))].sort((a, b) => a - b)
  const caption = `Overlaid curves: ${curves.map(({ label }) => label).join(', ')}`
  return (
    <Table.ScrollContainer minWidth={560} mt="md">
      <Table>
        <Table.Caption>{caption}</Table.Caption>
        <Table.Thead>
          <Table.Tr>
            <Table.Th scope="col">Curve · date</Table.Th>
            {tenors.map((tenor) => (
              <Table.Th key={tenor} scope="col" ta="right">
                {monthsLabel(tenor)}
              </Table.Th>
            ))}
          </Table.Tr>
        </Table.Thead>
        <Table.Tbody>
          {curves.map(({ key, label, points }) => {
            const values = new Map(points.map((point) => [point.months, point.value]))
            return (
              <Table.Tr key={key}>
                <Table.Th scope="row">{label}</Table.Th>
                {tenors.map((tenor) => {
                  const value = values.get(tenor)
                  return (
                    <Table.Td key={tenor} ta="right">
                      {value === null || value === undefined ? (
                        <VisuallyHidden>No value</VisuallyHidden>
                      ) : (
                        value.toFixed(3)
                      )}
                    </Table.Td>
                  )
                })}
              </Table.Tr>
            )
          })}
        </Table.Tbody>
      </Table>
    </Table.ScrollContainer>
  )
}
