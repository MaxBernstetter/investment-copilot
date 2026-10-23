import type { Ref } from 'react'
import { Box, Group, Pill } from '@mantine/core'
import { slotColor, type OverlayEntry } from './curveData'

/** A theme colour such as blue.8 as the CSS variable ColorSwatch needs; the chart takes the name itself. */
const cssColor = (slot: number) => `var(--mantine-color-${slotColor(slot).replace('.', '-')})`

type OverlayEntriesProps = {
  /** Entries in the order they were added, with their colour slot. */
  entries: (OverlayEntry & { slot: number })[]
  /** The legend label of each entry's curve, by curve id. */
  labelOf: (curveId: string) => string
  listRef: Ref<HTMLUListElement>
  onRemove: (index: number) => void
}

/** The pinned curves as removable pills, each with its colour in the chart. */
export default function OverlayEntries({ entries, labelOf, listRef, onRemove }: OverlayEntriesProps) {
  return (
    <Box
      component="ul"
      ref={listRef}
      aria-label="Overlaid curves"
      display="flex"
      mt={0}
      mb="md"
      p={0}
      style={{ flexWrap: 'wrap', gap: 'var(--mantine-spacing-xs)', listStyle: 'none' }}
    >
      {entries.map((entry, index) => {
        const text = `${labelOf(entry.curveId)} · ${entry.validDate}`
        return (
          <Pill
            key={`${entry.curveId}|${entry.validDate}`}
            component="li"
            withRemoveButton
            removeButtonProps={{ 'aria-label': `Remove ${text} from overlay`, 'aria-hidden': false, tabIndex: 0 }}
            onRemove={() => onRemove(index)}
          >
            <Group gap={6} wrap="nowrap" component="span">
              <Box component="span" aria-hidden w={10} h={10} display="inline-block" flex="none" style={{ borderRadius: '50%', backgroundColor: cssColor(entry.slot) }} />
              {text}
            </Group>
          </Pill>
        )
      })}
    </Box>
  )
}
