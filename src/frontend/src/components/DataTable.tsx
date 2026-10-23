import { useId, useRef, useState, type KeyboardEvent, type PointerEvent, type ReactNode } from 'react'
import { ActionIcon, Box, Button, Checkbox, Group, MultiSelect, Popover, RangeSlider, Stack, Table, Text, TextInput } from '@mantine/core'
import { IconColumns, IconFilter, IconX } from '@tabler/icons-react'

export type TableColumn<T> = {
  /** Stable id, used for the hidden set, the widths and the filters. */
  id: string
  /** Column header text; the empty string leaves the header visually empty. */
  header: string
  /** Cell content for one row. */
  cell: (row: T) => ReactNode
  /** Plain text the column filter matches, case-insensitively. Omit to make the column unfilterable. */
  filterText?: (row: T) => string
  /**
   * How the column filters. `text` (the default when `filterText` is set) is a substring match;
   * `number` is a range slider, `datetime` a from/to picker and `category` a multiselect. The last
   * three read `filterValue`: a number, an ISO date or UTC date-time string, or a category.
   */
  kind?: 'text' | 'number' | 'datetime' | 'category'
  /** The raw value behind the `number`, `datetime` and `category` filters; null rows never match an active filter. */
  filterValue?: (row: T) => number | string | null
  align?: 'left' | 'right'
  /** Renders the cell as the row header (`th scope="row"`). */
  rowHeader?: boolean
  /** Initial width in pixels. */
  width?: number
}

export const DEFAULT_WIDTH = 140
export const MIN_WIDTH = 64
/** Default width of a date or date-time column, wide enough for a from and a to picker side by side. */
export const DATETIME_WIDTH = 240
const KEY_STEP = 8

/** Keeps a column width at or above the minimum, in whole pixels. */
export function clampWidth(width: number): number {
  return Math.max(MIN_WIDTH, Math.round(width))
}

export type FilterState = string | [number, number] | { from: string; to: string } | string[]

/** The filter kind of a column, or undefined when it cannot be filtered. */
export function kindOf<T>(column: TableColumn<T>): NonNullable<TableColumn<T>['kind']> | undefined {
  const kind = column.kind ?? 'text'
  if (kind === 'text') return column.filterText === undefined ? undefined : 'text'
  return column.filterValue === undefined ? undefined : kind
}

/** An ISO date or date-time as `YYYY-MM-DDTHH:mm`, so dates and picker values compare as strings. */
function toMinute(value: string): string {
  return value.length <= 10 ? `${value}T00:00` : value.slice(0, 16)
}

/** True when the row passes the column's filter; an empty or untouched filter always passes. */
function matchesFilter<T>(row: T, column: TableColumn<T>, state: FilterState | undefined): boolean {
  const kind = kindOf(column)
  if (kind === undefined || state === undefined) return true
  if (kind === 'text') {
    const query = typeof state === 'string' ? state.trim().toLowerCase() : ''
    return query === '' || (column.filterText?.(row) ?? '').toLowerCase().includes(query)
  }
  const value = column.filterValue?.(row) ?? null
  if (kind === 'number') {
    if (!Array.isArray(state) || typeof state[0] !== 'number') return true
    return typeof value === 'number' && value >= state[0] && value <= (state[1] as number)
  }
  if (kind === 'datetime') {
    if (typeof state !== 'object' || Array.isArray(state)) return true
    if (state.from === '' && state.to === '') return true
    if (typeof value !== 'string') return false
    const minute = toMinute(value)
    return (state.from === '' || minute >= state.from) && (state.to === '' || minute <= state.to)
  }
  if (!Array.isArray(state) || state.length === 0) return true
  return typeof value === 'string' && (state as string[]).includes(value)
}

/** True when the row matches the filter of every column. */
export function matchesFilters<T>(row: T, columns: TableColumn<T>[], filters: Record<string, FilterState>): boolean {
  return columns.every((column) => matchesFilter(row, column, filters[column.id]))
}

/** The smallest and largest finite values of a number column, or undefined when there are none. */
function numberBounds<T>(column: TableColumn<T>, rows: T[]): [number, number] | undefined {
  const values = rows.map((row) => column.filterValue?.(row)).filter((v): v is number => typeof v === 'number' && Number.isFinite(v))
  return values.length === 0 ? undefined : [Math.min(...values), Math.max(...values)]
}

/** The distinct, sorted values of a category column. */
function categories<T>(column: TableColumn<T>, rows: T[]): string[] {
  const values = rows.map((row) => column.filterValue?.(row)).filter((v): v is string => typeof v === 'string' && v !== '')
  return [...new Set(values)].sort()
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

/** True when a filter has been set to something that narrows the rows. */
function isActive(state: FilterState | undefined): boolean {
  if (state === undefined) return false
  if (typeof state === 'string') return state.trim() !== ''
  if (Array.isArray(state)) return state.length > 0
  return state.from !== '' || state.to !== ''
}

type ColumnHeaderProps<T> = {
  column: TableColumn<T>
  width: number
  onResize: (width: number) => void
  rows: T[]
  filter: FilterState | undefined
  onFilter: (state: FilterState) => void
}

/** A filter icon in the column header; it opens the column's filter in a popup that can be closed. */
function HeaderFilter<T>({ column, rows, filter, onFilter }: Pick<ColumnHeaderProps<T>, 'column' | 'rows' | 'filter' | 'onFilter'>) {
  const [opened, setOpened] = useState(false)
  const name = column.header || column.id
  const active = isActive(filter)
  return (
    <Popover opened={opened} onChange={setOpened} position="bottom-start" withArrow shadow="md" trapFocus>
      <Popover.Target>
        <ActionIcon
          variant={active ? 'filled' : 'subtle'}
          color={active ? undefined : 'gray'}
          size="sm"
          aria-label={active ? `Filter ${name} (active)` : `Filter ${name}`}
          aria-expanded={opened}
          onClick={() => setOpened((current) => !current)}
        >
          <IconFilter size={14} aria-hidden />
        </ActionIcon>
      </Popover.Target>
      <Popover.Dropdown w={280}>
        <Stack gap="xs">
          <Group justify="space-between" wrap="nowrap">
            <Text size="sm" fw={600}>
              Filter {name}
            </Text>
            <ActionIcon variant="subtle" color="gray" size="sm" aria-label={`Close filter ${name}`} onClick={() => setOpened(false)}>
              <IconX size={14} aria-hidden />
            </ActionIcon>
          </Group>
          <FilterControl column={column} rows={rows} state={filter} onChange={onFilter} />
          {active && (
            <Button
              variant="default"
              size="compact-xs"
              onClick={() => onFilter(kindOf(column) === 'text' ? '' : kindOf(column) === 'datetime' ? { from: '', to: '' } : [])}
            >
              Clear filter
            </Button>
          )}
        </Stack>
      </Popover.Dropdown>
    </Popover>
  )
}

/**
 * A column header named by its text alone: the resize handle and the filter icon sit inside the cell,
 * so the cell is labelled by the text span rather than its content.
 */
function ColumnHeader<T>({ column, width, onResize, rows, filter, onFilter }: ColumnHeaderProps<T>) {
  const labelId = useId()
  return (
    <Table.Th scope="col" aria-labelledby={labelId} ta="left" style={{ width, position: 'relative' }}>
      <Group gap={4} wrap="nowrap" justify="space-between" pr={8}>
        <span id={labelId}>{column.header}</span>
        {kindOf(column) !== undefined && <HeaderFilter column={column} rows={rows} filter={filter} onFilter={onFilter} />}
      </Group>
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
  /** Height in pixels above which the body scrolls under a sticky header. */
  maxHeight?: number
  /** Fill the height of the parent instead (which needs a definite height); the body scrolls under the header. */
  fill?: boolean
}

/** Compact pickers, so a from and a to input fit side by side in one column. */
const PICKER_STYLES = { input: { paddingInline: 4, fontSize: 11, minWidth: 0 } }

type FilterControlProps<T> = {
  column: TableColumn<T>
  rows: T[]
  state: FilterState | undefined
  onChange: (state: FilterState) => void
}

/** The filter input that fits the column's kind. */
function FilterControl<T>({ column, rows, state, onChange }: FilterControlProps<T>) {
  const label = `Filter ${column.header || column.id}`
  const kind = kindOf(column)
  // The slider moves freely while dragged and filters the rows only once it is released.
  const [draft, setDraft] = useState<[number, number] | null>(null)
  if (kind === 'number') {
    const bounds = numberBounds(column, rows)
    if (bounds === undefined || bounds[0] === bounds[1]) return null
    const [min, max] = bounds
    const committed = Array.isArray(state) && typeof state[0] === 'number' ? state : [min, max]
    const value = draft ?? committed
    return (
      <RangeSlider
        size="xs"
        min={min}
        max={max}
        step={(max - min) / 100}
        minRange={0}
        label={(v) => v.toFixed(2)}
        value={value as [number, number]}
        onChange={setDraft}
        onChangeEnd={(range) => {
          setDraft(null)
          onChange(range)
        }}
        aria-label={label}
        thumbFromLabel={`${label} from`}
        thumbToLabel={`${label} to`}
        mb="xs"
      />
    )
  }
  if (kind === 'datetime') {
    const range = typeof state === 'object' && !Array.isArray(state) ? state : { from: '', to: '' }
    const dateOnly = rows.every((row) => {
      const v = column.filterValue?.(row)
      return typeof v !== 'string' || v.length <= 10
    })
    const type = dateOnly ? 'date' : 'datetime-local'
    return (
      <Group gap={4} wrap="nowrap" align="center">
        <TextInput
          size="xs"
          type={type}
          flex={1}
          miw={0}
          styles={PICKER_STYLES}
          aria-label={`${label} from`}
          value={range.from === '' ? '' : dateOnly ? range.from.slice(0, 10) : range.from}
          onChange={(event) => {
            const v = event.currentTarget.value
            onChange({ ...range, from: v === '' ? '' : toMinute(v) })
          }}
        />
        <Text size="xs" c="dimmed" aria-hidden>
          –
        </Text>
        <TextInput
          size="xs"
          type={type}
          flex={1}
          miw={0}
          styles={PICKER_STYLES}
          aria-label={`${label} to`}
          value={range.to === '' ? '' : dateOnly ? range.to.slice(0, 10) : range.to}
          onChange={(event) => {
            const v = event.currentTarget.value
            onChange({ ...range, to: v === '' ? '' : dateOnly ? `${v}T23:59` : toMinute(v) })
          }}
        />
      </Group>
    )
  }
  if (kind === 'category') {
    return (
      <MultiSelect
        size="xs"
        aria-label={label}
        placeholder={Array.isArray(state) && state.length > 0 ? undefined : 'All'}
        data={categories(column, rows)}
        value={Array.isArray(state) ? (state as string[]) : []}
        onChange={onChange}
        clearable
        comboboxProps={{ withinPortal: true }}
      />
    )
  }
  return (
    <TextInput
      size="xs"
      aria-label={label}
      placeholder="Filter"
      value={typeof state === 'string' ? state : ''}
      onChange={(event) => onChange(event.currentTarget.value)}
    />
  )
}

/**
 * A real table with three controls: a column selector (show or hide columns), a filter per column,
 * and resizable column widths. Hidden columns, widths and filters live in this component's state.
 * Each filterable column header carries a filter icon that opens that column's filter in a popup,
 * so the sticky header stays one row while the body scrolls.
 */
export default function DataTable<T>({
  caption,
  columns,
  rows,
  rowKey,
  striped = false,
  emptyText = 'No rows match the filters.',
  maxHeight = 520,
  fill = false,
}: DataTableProps<T>) {
  const [hiddenIds, setHiddenIds] = useState<string[]>([])
  const [widths, setWidths] = useState<Record<string, number>>({})
  const [filters, setFilters] = useState<Record<string, FilterState>>({})

  const visible = columns.filter((column) => !hiddenIds.includes(column.id))
  // A number range counts only while its slider is shown and narrower than the data, so a stale or full range never hides rows.
  const activeFilters = Object.fromEntries(
    Object.entries(filters).filter(([id, state]) => {
      const column = visible.find((candidate) => candidate.id === id)
      if (column === undefined || kindOf(column) !== 'number' || !Array.isArray(state)) return true
      const bounds = numberBounds(column, rows)
      const [from, to] = state as [number, number]
      return bounds !== undefined && bounds[0] !== bounds[1] && (from > bounds[0] || to < bounds[1])
    }),
  )
  const shown = rows.filter((row) => matchesFilters(row, visible, activeFilters))
  const widthOf = (column: TableColumn<T>) =>
    widths[column.id] ?? column.width ?? (kindOf(column) === 'datetime' ? DATETIME_WIDTH : DEFAULT_WIDTH)
  const tableWidth = visible.reduce((sum, column) => sum + widthOf(column), 0)

  const setColumnShown = (id: string, shownNow: boolean) => {
    setHiddenIds((ids) => (shownNow ? ids.filter((hidden) => hidden !== id) : [...ids, id]))
  }
  const setWidth = (id: string, width: number) => {
    setWidths((current) => ({ ...current, [id]: width }))
  }
  const setFilter = (id: string, query: FilterState) => {
    setFilters((current) => ({ ...current, [id]: query }))
  }

  return (
    <Stack gap="xs" h={fill ? '100%' : undefined} style={fill ? { minHeight: 0 } : undefined}>
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
      <Table.ScrollContainer
        minWidth={0}
        maxHeight={fill ? '100%' : maxHeight}
        style={fill ? { flex: 1, minHeight: 0 } : undefined}
        scrollAreaProps={{ viewportProps: { tabIndex: 0 } }}>
        <Table striped={striped} stickyHeader style={{ tableLayout: 'fixed', width: '100%', minWidth: tableWidth }}>
          {caption && <Table.Caption>{caption}</Table.Caption>}
          <Table.Thead>
            <Table.Tr>
              {visible.map((column) => (
                <ColumnHeader
                  key={column.id}
                  column={column}
                  width={widthOf(column)}
                  onResize={(width) => setWidth(column.id, width)}
                  rows={rows}
                  filter={filters[column.id]}
                  onFilter={(state) => setFilter(column.id, state)}
                />
              ))}
            </Table.Tr>
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
