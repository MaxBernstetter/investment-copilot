import { Anchor, Text } from '@mantine/core'
import { METHODOLOGY_URL } from '../config'

/** Explains the Unchecked badge under a table that shows one. */
export default function UncheckedNote() {
  return (
    <Text size="sm" c="dimmed" mt="sm">
      Unchecked means the quality checks have not run on the value yet.{' '}
      <Anchor size="sm" href={METHODOLOGY_URL} target="_blank" rel="noreferrer">
        How we check this
      </Anchor>
    </Text>
  )
}
