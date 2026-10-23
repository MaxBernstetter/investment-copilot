import { afterEach, describe, expect, it } from 'vitest'
import userEvent from '@testing-library/user-event'
import { cleanup, render, screen, within } from '../test/render'
import DataTable, { clampWidth, DEFAULT_WIDTH, matchesFilters, MIN_WIDTH, type TableColumn } from './DataTable'

type Row = { id: string; name: string; value: number }

const rows: Row[] = [
  { id: 'a', name: 'Alpha', value: 1.25 },
  { id: 'b', name: 'Beta', value: 2.5 },
  { id: 'c', name: 'Gamma', value: 3.75 },
]

const columns: TableColumn<Row>[] = [
  { id: 'name', header: 'Name', rowHeader: true, cell: (row) => row.name, filterText: (row) => row.name },
  { id: 'value', header: 'Value', align: 'right', cell: (row) => row.value.toFixed(2), filterText: (row) => row.value.toFixed(2) },
  { id: 'note', header: 'Note', cell: (row) => `note ${row.id}` },
]

function renderTable() {
  return render(
    <DataTable caption="Sample rows" columns={columns} rows={rows} rowKey={(row) => row.id} />,
  )
}

/** The names of the column headers in the first header row; the filter row is the second. */
function headerNames(): string[] {
  const [headerRow] = within(screen.getAllByRole('rowgroup')[0]).getAllByRole('row')
  return within(headerRow)
    .getAllByRole('columnheader')
    .map((header) => header.textContent ?? '')
}

describe('DataTable', () => {
  afterEach(cleanup)

  it('renders a real table with a caption, column headers and one row per item', () => {
    renderTable()
    expect(screen.getByRole('table', { name: 'Sample rows' })).toBeVisible()
    expect(headerNames()).toEqual(['Name', 'Value', 'Note'])
    expect(screen.getByRole('columnheader', { name: 'Value' })).toBeVisible()
    expect(screen.getByRole('rowheader', { name: 'Alpha' })).toBeVisible()
    expect(screen.getAllByRole('row').length).toBe(1 + 1 + rows.length)
  })

  it('hides a column from the Columns menu and shows it again', async () => {
    const user = userEvent.setup()
    renderTable()
    await user.click(screen.getByRole('button', { name: 'Columns' }))
    await user.click(screen.getByRole('checkbox', { name: 'Value' }))
    expect(headerNames()).toEqual(['Name', 'Note'])
    await user.click(screen.getByRole('checkbox', { name: 'Value' }))
    expect(headerNames()).toEqual(['Name', 'Value', 'Note'])
  })

  it('does not let the last visible column be hidden', async () => {
    const user = userEvent.setup()
    renderTable()
    await user.click(screen.getByRole('button', { name: 'Columns' }))
    await user.click(screen.getByRole('checkbox', { name: 'Name' }))
    await user.click(screen.getByRole('checkbox', { name: 'Value' }))
    expect(screen.getByRole('checkbox', { name: 'Note' })).toBeDisabled()
    expect(headerNames()).toEqual(['Note'])
  })

  it('filters rows by the text of one column, case-insensitively', async () => {
    const user = userEvent.setup()
    renderTable()
    await user.type(screen.getByRole('textbox', { name: 'Filter Name' }), 'AMM')
    expect(screen.getAllByRole('rowheader').map((cell) => cell.textContent)).toEqual(['Gamma'])
  })

  it('shows the empty text when the filters hide every row', async () => {
    const user = userEvent.setup()
    renderTable()
    await user.type(screen.getByRole('textbox', { name: 'Filter Value' }), '9')
    expect(screen.getByText('No rows match the filters.')).toBeVisible()
    expect(screen.queryByRole('rowheader')).not.toBeInTheDocument()
  })

  it('has no filter input for a column without filter text', () => {
    renderTable()
    expect(screen.queryByRole('textbox', { name: 'Filter Note' })).not.toBeInTheDocument()
  })

  it('resizes a column from its separator with the arrow keys, never below the minimum', async () => {
    const user = userEvent.setup()
    renderTable()
    const separator = screen.getByRole('separator', { name: 'Resize Value' })
    expect(separator).toHaveAttribute('aria-valuenow', String(DEFAULT_WIDTH))
    separator.focus()
    await user.keyboard('{ArrowRight}')
    expect(screen.getByRole('separator', { name: 'Resize Value' })).toHaveAttribute(
      'aria-valuenow',
      String(DEFAULT_WIDTH + 8),
    )
    for (let step = 0; step < 40; step += 1) await user.keyboard('{ArrowLeft}')
    expect(screen.getByRole('separator', { name: 'Resize Value' })).toHaveAttribute('aria-valuenow', String(MIN_WIDTH))
  })
})

describe('DataTable helpers', () => {
  it('clamps a width to the minimum and rounds it', () => {
    expect(clampWidth(10)).toBe(MIN_WIDTH)
    expect(clampWidth(150.6)).toBe(151)
  })

  it('matches a row only when every non-empty filter on a filterable column is contained in its text', () => {
    const row = rows[0]
    expect(matchesFilters(row, columns, {})).toBe(true)
    expect(matchesFilters(row, columns, { name: 'alp', value: '1.2' })).toBe(true)
    expect(matchesFilters(row, columns, { name: 'beta' })).toBe(false)
    expect(matchesFilters(row, columns, { note: 'anything' })).toBe(true)
  })
})
