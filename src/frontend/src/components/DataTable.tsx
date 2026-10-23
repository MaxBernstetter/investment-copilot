import { useId, useRef, useState, type KeyboardEvent, type PointerEvent, type ReactNode } from 'react'
import { Box, Button, Checkbox, Group, Popover, Stack, Table, Text, TextInput } from '@mantine/core'
import { IconColumns } from '@tabler/icons-react'

export type TableColumn<T> = {
  /** Stable id, used for the hidden set, the widths and the filters. */
  id: string
  /** Column header text; the empty string leaves the header visually empty. */
  header: string
  /** Cell content for one row. */
  cell: (row: T) => ReactNode
  /** Plain text the column filter matches, case-insensitively. Omit to make the column unfilterable. */
  filterText?: (row: T) => string
  align?: 'left' | 'right'
  /** Renders the cell as the row header (`th scope="row"`). */
  rowHeader?: boolean
  /** Initial width in pixels. */
  width?: number
}

export const DEFAULT_WIDTH = 140
export const MIN_WIDTH = 64
const KEY_STEP = 8

/** Keeps a column width at or above the minimum, in whole pixels. */
export function clampWidth(width: number): number {
  return Math.max(MIN_WIDTH, Math.round(width))
}

/** True when the row matches every non-empty filter on a column that has filter text. */
export function matchesFilters<T>(row: T, columns: TableColumn<T>[], filters: Record<string, string>): boolean {
  return columns.every((column) => {
    const query = (filters[column.id] ?? '').trim().toLowerCase()
    if (query === '' || column.filterText === undefined) return true
    return column.filterText(row).toLowerCase().includes(query)
  })
}

type ResizeHandleProps = {
  label: string
  width: number
  onChange: (width: number) => void
}

/** A focusable vertical separator on the right edge of a header cell: drag it, or use the arrow keys. */
function ResizeHandle({ label, width, onChange }: ResizeHandleProps) {
  const drag = useRef<{ startX: number; startWidth: number } | null>(null)

  const onPointerDown = (event: PointerEvent<HTMLSpanElement>) => {
    drag.current = { startX: event.clientX, startWidth: width }
    event.currentTarget.setPointerCapture?.(event.pointerId)
  }
  const onPointerMove = (event: PointerEvent<HTMLSpanElement>) => {
    if (drag.current) onChange(clampWidth(drag.current.startWidth + event.clientX - drag.current.startX))
  }
  const endDrag = (event: PointerEvent<HTMLSpanElement>) => {
    drag.current = null
    event.currentTarget.releasePointerCapture?.(event.pointerId)
  }
  const onKeyDown = (event: KeyboardEvent<HTMLSpanElement>) => {
    if (event.key === 'ArrowLeft' || event.key === 'ArrowRight') {
      event.preventDefault()
      const step = event.key === 'ArrowLeft' ? -KEY_STEP : KEY_STEP
      onChange(clampWidth(width + step))
    }
  }

  return (
    <Box
      component="span"
      role="separator"
      tabIndex={0}
      aria-orientation="vertical"
      aria-label={`Resize ${label}`}
      aria-valuenow={width}
      aria-valuemin={MIN_WIDTH}
      onPointerDown={onPointerDown}
      onPointerMove={onPointerMove}
      onPointerUp={endDrag}
      onPointerCancel={endDrag}
      onKeyDown={onKeyDown}
      style={{
        position: 'absolute',
        top: 0,
        right: 0,
        bottom: 0,
        width: 8,
        cursor: 'col-resize',
        touchAction: 'none',
      }}
    />
  )
}

type ColumnHeaderProps<T> = {
  column: TableColumn<T>
  width: number
  onResize: (width: number) => void
}

/**
 * A column header named by its text alone: the resize handle sits inside the cell, so the cell is
 * labelled by the text span rather than its content.
 */
function ColumnHeader<T>({ column, width, onResize }: ColumnHeaderProps<T>) {
  const labelId = useId()
  return (
    <Table.Th
      scope="col"
      aria-labelledby={labelId}
      ta={column.align === 'right' ? 'right' : undefined}
      style={{ width, position: 'relative' }}
    >
      <span id={labelId}>{column.header}</span>
      <ResizeHandle label={column.header || column.id} width={width} onChange={onResize} />
    </Table.Th>
  )
}

type DataTableProps<T> = {
  /** Table caption, which names the table for assistive technology. */
  caption?: string
  columns: TableColumn<T>[]
  rows: T[]
  rowKey: (row: T) => string
  striped?: boolean
  /** Shown in place of the rows when the filters hide every row. */
  emptyText?: string
}

/**
 * A real table with three controls: a column selector (show or hide columns), a filter per column,
 * and resizable column widths. Hidden columns, widths and filters live in this component's state.
 * The header row keeps the column headers; the filter row under it holds one input per filterable column
 * and uses plain cells, so the column headers stay the only columnheaders.
 */
export default function DataTable<T>({
  caption,
  columns,
  rows,
  rowKey,
  striped = false,
  emptyText = 'No rows match the filters.',
}: DataTableProps<T>) {
  const [hiddenIds, setHiddenIds] = useState<string[]>([])
  const [widths, setWidths] = useState<Record<string, number>>({})
  const [filters, setFilters] = useState<Record<string, string>>({})

  const visible = columns.filter((column) => !hiddenIds.includes(column.id))
  const filterable = visible.some((column) => column.filterText !== undefined)
  const shown = rows.filter((row) => matchesFilters(row, visible, filters))
  const widthOf = (column: TableColumn<T>) => widths[column.id] ?? column.width ?? DEFAULT_WIDTH
  const tableWidth = visible.reduce((sum, column) => sum + widthOf(column), 0)

  const setColumnShown = (id: string, shownNow: boolean) => {
    setHiddenIds((ids) => (shownNow ? ids.filter((hidden) => hidden !== id) : [...ids, id]))
  }
  const setWidth = (id: string, width: number) => {
    setWidths((current) => ({ ...current, [id]: width }))
  }
  const setFilter = (id: string, query: string) => {
    setFilters((current) => ({ ...current, [id]: query }))
  }

  return (
    <Stack gap="xs">
      {columns.length > 1 && (
        <Group justify="flex-end">
          <Popover position="bottom-end" withArrow shadow="md">
            <Popover.Target>
              <Button variant="default" size="xs" leftSection={<IconColumns size={14} aria-hidden />}>
                Columns
              </Button>
            </Popover.Target>
            <Popover.Dropdown>
              <Stack gap="xs">
                {columns.map((column) => {
                  const isShown = !hiddenIds.includes(column.id)
                  return (
                    <Checkbox
                      key={column.id}
                      label={column.header || column.id}
                      checked={isShown}
                      disabled={isShown && visible.length === 1}
                      onChange={(event) => setColumnShown(column.id, event.currentTarget.checked)}
                    />
                  )
                })}
              </Stack>
            </Popover.Dropdown>
          </Popover>
        </Group>
      )}
      <Table.ScrollContainer minWidth={0} scrollAreaProps={{ viewportProps: { tabIndex: 0 } }}>
        <Table striped={striped} style={{ tableLayout: 'fixed', width: '100%', minWidth: tableWidth }}>
          {caption && <Table.Caption>{caption}</Table.Caption>}
          <Table.Thead>
            <Table.Tr>
              {visible.map((column) => (
                <ColumnHeader
                  key={column.id}
                  column={column}
                  width={widthOf(column)}
                  onResize={(width) => setWidth(column.id, width)}
                />
              ))}
            </Table.Tr>
            {filterable && (
              <Table.Tr>
                {visible.map((column) => (
                  <Table.Td key={column.id} style={{ width: widthOf(column) }}>
                    {column.filterText && (
                      <TextInput
                        size="xs"
                        aria-label={`Filter ${column.header || column.id}`}
                        placeholder="Filter"
                        value={filters[column.id] ?? ''}
                        onChange={(event) => setFilter(column.id, event.currentTarget.value)}
                      />
                    )}
                  </Table.Td>
                ))}
              </Table.Tr>
            )}
          </Table.Thead>
          <Table.Tbody>
            {shown.length === 0 ? (
              <Table.Tr>
                <Table.Td colSpan={visible.length}>
                  <Text size="sm" c="dimmed">
                    {emptyText}
                  </Text>
                </Table.Td>
              </Table.Tr>
            ) : (
              shown.map((row) => (
                <Table.Tr key={rowKey(row)}>
                  {visible.map((column) => {
                    const align = column.align === 'right' ? 'right' : undefined
                    return column.rowHeader ? (
                      <Table.Th key={column.id} scope="row" ta={align}>
                        {column.cell(row)}
                      </Table.Th>
                    ) : (
                      <Table.Td key={column.id} ta={align}>
                        {column.cell(row)}
                      </Table.Td>
                    )
                  })}
                </Table.Tr>
              ))
            )}
          </Table.Tbody>
        </Table>
      </Table.ScrollContainer>
    </Stack>
  )
}
